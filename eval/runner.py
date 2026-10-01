"""Runner de la evaluación end-to-end (Fase 6.2, Paso 2 de docs/Rol B - ML/guia_fase_6_2_a_6_5.md).

Corre los casos de eval/cases/<split>.jsonl contra el backend en proceso (TestClient) con el
cliente simulado de eval/cases/SCHEMA.md §1.3, y escribe eval/reports/<run_id>/ con el formato
de eval/FORMATO_RESULTADOS.md (manifest.json + results.jsonl; los graders escriben el resto).

    python -m eval.runner                                   # dev, S, con y sin Gemini, 1 corrida
    python -m eval.runner --llm without_gemini --cases dev-normal-001 dev-ambiguo-001
    python -m eval.runner --split heldout --system S B1 --runs 3 --stage final

Una corrida = un sistema × una configuración de LLM × un número de corrida × un split. Cada una
corre en un subproceso propio, porque la configuración (GEMINI_API_KEY, el modelo de intención,
OPS_DB_PATH) se lee una sola vez al importar el backend.

Siempre: OPS_DB_PATH=:memory: (nunca toca data/ops.sqlite), FAULT_INJECTION=true, base operativa
limpia antes de cada caso (reset_store) y token emitido con auth.issue_token.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval" / "reports"

# Hash de eval/cases/heldout.jsonl congelado en 90bccf2 (Paso 10 de la 6.1). Si no coincide, no se corre.
HELDOUT_SHA256 = "4560d282690ae4923bb4e627005c354dd45b74a25482a64758c92cb3366b7cd3"

TERMINALES = {"CERRAR", "HANDOFF", "ABSTENERSE", "INFORMAR_ESTADO"}
LLM_CONFIGS = ("with_gemini", "without_gemini")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ahora() -> datetime:
    return datetime.now(timezone.utc)


# --- Entorno de cada corrida ----------------------------------------------------------------------


def entorno(system: str, llm: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update({"OPS_DB_PATH": ":memory:", "FAULT_INJECTION": "true", "DEMO_MODE": "true"})
    if llm == "without_gemini":
        env["GEMINI_API_KEY"] = ""          # vacía en el entorno: load_dotenv no la pisa
    if system == "B1":
        env["NLU_MODE"] = "keywords"
        # Mientras NLU_MODE no exista en el backend (pedido a Alina), el clasificador que no carga
        # deja el NLU en el stub de palabras clave (FORMATO_RESULTADOS.md §6). El worker verifica
        # en /health que de verdad quedó en stub-keywords-0.
        env["INTENT_MODEL_PATH"] = "/no/existe/b1"
    return env


def hay_llave_gemini() -> bool:
    if os.environ.get("GEMINI_API_KEY"):
        return True
    try:
        from dotenv import dotenv_values
        return bool(dotenv_values(ROOT / ".env").get("GEMINI_API_KEY"))
    except Exception:
        return False


# --- Worker: una corrida en este proceso ----------------------------------------------------------


def worker(a: argparse.Namespace) -> int:
    sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

    from fastapi.testclient import TestClient

    from app.auth import issue_token
    from app.config import get_policy, get_settings
    from app.main import app
    from app.nlu import extract_llm, intent_llm
    from app.responder import compose
    from app.schemas import DisputeCase, HandoffPackage, Trace
    from app.store import flush, reset_store, store
    from app.tools import data_source
    from app.tools.cases import _COMPLAINT_CATEGORY
    from eval.cases.schema import Case
    from eval.formato import CaseResult, Flags, Manifest, Turn, Versions, append_jsonl, write_json

    s = get_settings()
    if a.llm == "with_gemini" and not s.gemini_api_key:
        print("ERROR: with_gemini sin GEMINI_API_KEY", file=sys.stderr)
        return 2
    if a.llm == "without_gemini" and s.gemini_api_key:
        print("ERROR: without_gemini pero el backend ve una GEMINI_API_KEY", file=sys.stderr)
        return 2

    cases_file = ROOT / "eval" / "cases" / f"{a.split}.jsonl"
    cases_sha = sha256(cases_file)
    if a.split == "heldout" and cases_sha != HELDOUT_SHA256:
        print(f"ERROR: heldout.jsonl cambió desde el congelado ({cases_sha[:12]} ≠ {HELDOUT_SHA256[:12]})",
              file=sys.stderr)
        return 2

    casos = [Case.model_validate_json(l) for l in cases_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.cases:
        por_id = {c.case_id: c for c in casos}
        faltan = [c for c in a.cases if c not in por_id]
        if faltan:
            print(f"ERROR: casos que no están en {cases_file.name}: {faltan}", file=sys.stderr)
            return 2
        casos = [por_id[c] for c in a.cases]
    correr = [c for c in casos if c.setup.llm in ("both", a.llm)]
    saltados = [c.case_id for c in casos if c not in correr]

    client = TestClient(app)
    health = client.get("/api/health").json()
    nlu_mode = "keywords" if a.system == "B1" else "full"
    if a.system == "B1" and health["intent_model"] != "stub-keywords-0":
        print(f"ERROR: B1 tiene que correr con el stub y /health dice {health['intent_model']}", file=sys.stderr)
        return 2

    git = lambda *c: subprocess.run(["git", *c], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    inicio = ahora()
    run_id = f"{inicio:%Y%m%dT%H%M%SZ}-{a.system}-{a.llm}-r{a.run_number}-{a.split}"
    out = REPORTS / run_id
    out.mkdir(parents=True, exist_ok=False)
    manifest = Manifest(
        run_id=run_id, system=a.system, llm=a.llm, run_number=a.run_number, stage=a.stage, split=a.split,
        cases_file=str(cases_file.relative_to(ROOT)), cases_sha256=cases_sha,
        case_ids=[c.case_id for c in correr], skipped_case_ids=saltados,
        git_commit=git("rev-parse", "HEAD"), git_dirty=bool(git("status", "--porcelain")),
        versions=Versions(
            policy_version=health["policy_version"], intent_model=health["intent_model"],
            llm_model=health["llm_model"], data_source=data_source.source_name(),
            data_manifest=health["data_manifest"],
            data_run=",".join(sorted({c.provenance.data_run for c in correr if c.provenance.data_run})) or "-",
            nlu_mode=nlu_mode,
            prompts={"extraccion": extract_llm.PROMPT_VERSION, "intencion": intent_llm.PROMPT_VERSION,
                     "redaccion": compose.PROMPT_VERSION, "resumen_handoff": compose.PROMPT_RESUMEN_VERSION}),
        env={k: os.environ.get(k, "(no fijada)") for k in
             ("OPS_DB_PATH", "FAULT_INJECTION", "DEMO_MODE", "NLU_MODE", "INTENT_MODEL_PATH", "GEMINI_MODEL")}
            | {"GEMINI_API_KEY": "(fijada)" if s.gemini_api_key else "(vacía)"},
        started_at=inicio,
    )
    write_json(out / "manifest.json", manifest)

    def bearer(sub: str, role: str, lang: str) -> dict:
        return {"Authorization": f"Bearer {issue_token(sub, role, lang)[0]}"}

    def sembrar(caso: Case) -> None:
        """setup.open_cases → DisputeCase en el store operativo, creado ahora (cuenta para R11)."""
        sla = get_policy()["sla_days_by_priority"]
        for sc in caso.setup.open_cases:
            tx = data_source.transaction(caso.customer_id, sc.transaction_id)
            if tx is None:
                raise ValueError(f"open_cases: {sc.transaction_id} no es de {caso.customer_id}")
            cat, sub = _COMPLAINT_CATEGORY[sc.dispute_type]
            creado = ahora()
            cid = store.next_id("DSP")
            store.cases[cid] = DisputeCase(
                case_id=cid, customer_id=caso.customer_id, transaction_id=sc.transaction_id,
                product_id=tx["product_id"], dispute_type=sc.dispute_type, category=cat, subcategory=sub,
                priority=sc.priority, status=sc.status, rule_id="R12", policy_version="sembrado-eval",
                language="pt" if caso.language == "pt" else "es",
                created_at=creado, sla_due_at=creado + timedelta(days=sla[sc.priority]))
        flush()

    def correr_caso(caso: Case) -> CaseResult:
        reset_store()                                     # base operativa limpia
        t0 = ahora()
        rr, setup = caso.response_rules, caso.setup
        script = list(caso.script)
        primer_msg = next((e for e in script if e.kind == "message"), None)
        lang = primer_msg.language if primer_msg else ("es" if caso.language == "mix" else caso.language)
        st = {"h": bearer(caso.customer_id, "customer", lang), "conv": None, "idx": 0,
              "lang": lang, "expirada": False}
        turns: list[Turn] = []
        flags = Flags()
        status, err = "completed", None

        def enviar(body: dict, reason: str, en_confirmacion: bool = False, confirma: str | None = None):
            n = len(turns) + 1
            forzar = [f.tool for f in setup.faults
                      if f.at == "every_turn" or f.at == n
                      or (f.at == "on_confirm" and confirma and f.action in (None, confirma))]
            ex = setup.expire_session
            expira = (ex is not None and not st["expirada"]
                      and (ex.before_turn == n or (ex.before_turn == "on_confirm" and en_confirmacion)))
            if expira:
                r = client.post("/api/auth/demo/expire", headers=st["h"])
                if r.status_code != 204:
                    raise RuntimeError(f"/auth/demo/expire devolvió {r.status_code}")
                st["expirada"] = True
            hh = dict(st["h"])
            if forzar:
                hh["X-Fault-Inject"] = ",".join(forzar)
            req = {"conversation_id": st["conv"], "message": None, "ui_action": None, **body}
            t = time.perf_counter()
            r = client.post("/api/chat", headers=hh, json=req)
            ms = int((time.perf_counter() - t) * 1000)
            data = r.json()
            turns.append(Turn(n=n, reason=reason, request=req, fault_injected=forzar, session_expired_before=expira,
                              http_status=r.status_code, response=data if r.status_code == 200 else None,
                              error=data if r.status_code != 200 else None, client_latency_ms=ms))
            if r.status_code == 200:
                st["conv"] = data["conversation_id"]
            return r.status_code, data

        def guion():
            if st["idx"] >= len(script):
                return None
            i = st["idx"]
            e = script[i]
            st["idx"] += 1
            if e.kind == "message":
                st["lang"] = e.language
                return {"message": e.text}, f"script[{i}]"
            return {"ui_action": {"type": "select_transaction", "transaction_id": e.transaction_id}}, f"script[{i}]"

        def elegir_esperada(ui: dict):
            ids = [o["transaction_id"] for o in ui.get("options", [])]
            tid = caso.expected.transaction_id
            if tid is not None and tid in ids:
                return {"ui_action": {"type": "select_transaction", "transaction_id": tid}}, "select expected"
            flags.identification_failed = True
            return {"message": rr.on_options.none_text[st["lang"]]}, "none (esperada no está)"

        def siguiente(code: int, data: dict):
            """Reglas de respuesta de SCHEMA.md §1.3. Devuelve (body, reason, kwargs) o None = termina."""
            # 1. 401 SESSION_EXPIRED
            if code == 401:
                ex = setup.expire_session
                if (data.get("error") or {}).get("code") == "SESSION_EXPIRED" and ex and ex.resume:
                    st["h"] = bearer(caso.customer_id, "customer", st["lang"])
                    ultimo = turns[-1]
                    body = ultimo.request.model_dump(mode="json", exclude={"conversation_id"})
                    return body, f"reauth ({ultimo.reason})", {}
                return None
            if code != 200:                     # 4xx/5xx del backend: queda en el turno, el caso termina
                return None
            # 2. Estado terminal
            if data["state"] in TERMINALES:
                return None
            ui = data.get("ui") or {}
            # 3. Opciones de transacción
            if ui.get("type") == "transaction_options":
                sel = rr.on_options.select
                if sel == "next_script_turn":
                    nxt = guion()
                    if nxt:
                        return nxt[0], nxt[1] + " (opciones)", {}
                    sel = "expected"
                if sel == "expected":
                    return (*elegir_esperada(ui), {})
                return {"message": rr.on_options.none_text[st["lang"]]}, "none", {}
            # 4. Confirmación
            if ui.get("type") == "confirmation":
                if rr.on_confirmation.script_first:
                    nxt = guion()
                    if nxt:
                        return nxt[0], nxt[1] + " (confirmación pendiente)", {}
                pa = ui["pending_action"]
                dec = getattr(rr.on_confirmation, pa["action"], "confirm")
                if rr.on_confirmation.via == "button":
                    body = {"ui_action": {"type": dec, "pending_action_id": pa["pending_action_id"]}}
                else:
                    body = {"message": rr.on_confirmation.texts[dec][st["lang"]]}
                kw = {"en_confirmacion": True, "confirma": pa["action"] if dec == "confirm" else None}
                return body, f"{dec} {pa['action']}" + (" (texto)" if rr.on_confirmation.via == "text" else ""), kw
            # 5. Cualquier otra respuesta
            if rr.on_more_info == "next_script_turn":
                nxt = guion()
                if nxt:
                    return nxt[0], nxt[1], {}
            return None

        try:
            sembrar(caso)
            body, reason = guion()
            code, data = enviar(body, reason)
            while True:
                nxt = siguiente(code, data)
                if nxt is None:
                    break
                # 6. max_turns: había algo más que mandar y ya no quedan turnos
                if len(turns) >= rr.max_turns:
                    flags.max_turns_reached = True
                    status = "max_turns"
                    break
                code, data = enviar(nxt[0], nxt[1], **nxt[2])
        except Exception:
            status, err = "runner_error", traceback.format_exc(limit=6)

        trace = None
        ok = [t.response for t in turns if t.response is not None]
        if ok:
            trace = store.traces.get(ok[-1].trace_id)
        try:
            leer = bearer(caso.customer_id, "customer", "es")   # el token del caso puede estar revocado
            cases = client.get("/api/cases", headers=leer).json()["cases"]
            agente = bearer(s.demo_agent_id, "agent", "es")
            handoffs = [client.get(f"/api/handoffs/{hid}", headers=agente).json() for hid in list(store.handoffs)]
        except Exception:
            cases, handoffs = [], []
            if status != "runner_error":
                status, err = "runner_error", traceback.format_exc(limit=6)

        tt = trace.turns if trace else []
        return CaseResult(
            run_id=run_id, case_id=caso.case_id, category=caso.category, language=caso.language,
            segment=caso.segment, status=status, runner_error=err, flags=flags, turns=turns,
            trace=Trace.model_validate(trace.model_dump()) if trace else None,
            cases=[DisputeCase.model_validate(c) for c in cases],
            handoffs=[HandoffPackage.model_validate(h) for h in handoffs],
            latency_ms=sum(t.latency_ms for t in tt), tokens_in=sum(t.tokens_in for t in tt),
            tokens_out=sum(t.tokens_out for t in tt), cost_usd=round(sum(t.cost_usd for t in tt), 6),
            started_at=t0)

    cuenta = {"completed": 0, "max_turns": 0, "runner_error": 0}
    for i, caso in enumerate(correr, 1):
        res = correr_caso(caso)
        append_jsonl(out / "results.jsonl", res)
        cuenta[res.status] += 1
        estado = res.turns[-1].response.state if res.turns and res.turns[-1].response else (
            f"HTTP {res.turns[-1].http_status}" if res.turns else "-")
        print(f"  [{i:>3}/{len(correr)}] {caso.case_id:<34} {res.status:<12} {len(res.turns)} turnos  {estado}",
              flush=True)
        if res.runner_error:
            print("      " + res.runner_error.strip().splitlines()[-1], flush=True)

    manifest.finished_at = ahora()
    manifest.n_completed, manifest.n_max_turns, manifest.n_runner_error = (
        cuenta["completed"], cuenta["max_turns"], cuenta["runner_error"])
    write_json(out / "manifest.json", manifest)
    print(f"RUN_DIR {out.relative_to(ROOT)}", flush=True)
    return 0


# --- Orquestación: un subproceso por corrida ------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Runner de la evaluación end-to-end (Fase 6.2)")
    p.add_argument("--split", choices=["dev", "heldout"], default="dev")
    p.add_argument("--system", nargs="+", choices=["S", "B1"], default=["S"])
    p.add_argument("--llm", choices=[*LLM_CONFIGS, "both"], default="both",
                   help="configuración de LLM para S (B1 siempre corre without_gemini)")
    p.add_argument("--runs", type=int, default=1, choices=[1, 2, 3])
    p.add_argument("--cases", nargs="+", help="solo estos case_id (para depurar)")
    p.add_argument("--stage", choices=["debug", "primera", "final"],
                   help="debug (dev), primera (Paso 9) o final (Paso 11). Default: debug en dev, primera en heldout")
    # interno: una sola corrida en este proceso
    p.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--_llm", help=argparse.SUPPRESS)
    p.add_argument("--_run", type=int, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    a.stage = a.stage or ("debug" if a.split == "dev" else "primera")

    if a._worker:
        a.system, a.llm, a.run_number = a.system[0], a._llm, a._run
        return worker(a)

    if a.split == "heldout" and a.stage == "debug":
        p.error("el held-out no se corre en stage=debug (regla de oro 1: se depura en dev)")

    plan = []
    for system in a.system:
        llms = ["without_gemini"] if system == "B1" else (list(LLM_CONFIGS) if a.llm == "both" else [a.llm])
        for llm in llms:
            for run in range(1, a.runs + 1):
                plan.append((system, llm, run))

    resumen, fallo = [], False
    for system, llm, run in plan:
        print(f"\n== {system} · {llm} · r{run} · {a.split} ==", flush=True)
        if llm == "with_gemini" and not hay_llave_gemini():
            print("   SALTADA: no hay GEMINI_API_KEY en el entorno ni en .env")
            resumen.append((system, llm, run, None))
            fallo = True
            continue
        cmd = [sys.executable, "-m", "eval.runner", "--_worker", "--split", a.split, "--system", system,
               "--_llm", llm, "--_run", str(run), "--stage", a.stage]
        if a.cases:
            cmd += ["--cases", *a.cases]
        proc = subprocess.Popen(cmd, cwd=ROOT, env=entorno(system, llm), stdout=subprocess.PIPE,
                                text=True, bufsize=1)
        run_dir = None
        for linea in proc.stdout:
            if linea.startswith("RUN_DIR "):
                run_dir = ROOT / linea.split(" ", 1)[1].strip()
            else:
                print(linea, end="", flush=True)
        if proc.wait() != 0 or run_dir is None:
            print(f"   la corrida terminó con código {proc.returncode}")
            resumen.append((system, llm, run, None))
            fallo = True
            continue
        resumen.append((system, llm, run, json.loads((run_dir / "manifest.json").read_text())))

    print("\nResumen")
    print(f"  {'corrida':<52} {'casos':>5} {'terminaron':>10} {'max_turns':>9} {'error':>5} {'saltados':>8}")
    for system, llm, run, m in resumen:
        if m is None:
            print(f"  {system}-{llm}-r{run}: no corrió")
            continue
        print(f"  {m['run_id']:<52} {len(m['case_ids']):>5} {m['n_completed']:>10} {m['n_max_turns']:>9} "
              f"{m['n_runner_error']:>5} {len(m['skipped_case_ids']):>8}")
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
