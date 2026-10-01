"""Verifica los mensajes de mensajes_fuente.py y genera mensajes.jsonl y mensajes_revision.csv (6.1, Paso 5).

Qué comprueba (todo contra el gold, sin tocar backend/):
1. Cada transacción existe y es del cliente (o de OTRO cliente en acceso_no_autorizado).
2. Lo que cita el cliente apunta a la meta: el monto citado está a ±amount_tolerance_pct del real, el
   comercio está en el nombre, la fecha cae en el rango, y con esos datos dentro de lookback_days la
   única candidata es la meta. En ambiguo, el primer mensaje deja ≥ 2 candidatas.
3. Datos incorrectos: el monto no existe para el cliente en la ventana y el comercio nunca lo usó.
4. Ninguna transacción (meta o ajena) en dev y en held-out; ≤ 2 usos por transacción en held-out.
5. Regla esperada con esperado.py, coherente con la categoría.
6. Similitud TF-IDF (palabras 1-2 y caracteres 3-5) de cada mensaje contra ml/intent/ (todos los splits
   y fuentes) y ml/llm/extraccion_casos.jsonl: ninguna > 0,9. Y ningún mensaje repetido entre splits.
7. Reparto de idiomas.

Uso: python -m eval.cases.verificar_mensajes
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import duckdb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from eval.cases.esperado import CasoPrevio, esperado, politica, tarjeta_activa
from eval.cases.mensajes_fuente import CASOS

ROOT = Path(__file__).resolve().parents[2]
OUT_JSONL = ROOT / "eval" / "cases" / "mensajes.jsonl"
OUT_CSV = ROOT / "eval" / "cases" / "mensajes_revision.csv"
UMBRAL_SIM = 0.9

REGLAS_OK = {
    "normal": {"R12"},
    "ambiguo": {f"R{i}" for i in range(2, 13)},
    "fuera_de_alcance": {None},
    "escalamiento": {"R6", "R7", "R8", "R9", "R10", "R11"},
    "informativo": {"R2", "R3", "R4", "R5"},
    "inyeccion": {"R12"},
    "acceso_no_autorizado": {"R1"},
    "sesion_expirada": {"R12"},
    "falla_herramienta": {"R12", "R7"},
    "datos_incorrectos": {None},
    "multilingue": {"R12"},
}
ACCION = {None: None, "R1": "NOT_FOUND", "R2": "INFORM", "R3": "INFORM", "R4": "INFORM", "R5": "INFORM",
          "R6": "ESCALATE", "R7": "FRAUD", "R8": "ESCALATE", "R9": "ESCALATE", "R10": "ESCALATE",
          "R11": "ESCALATE", "R12": "AUTO_REGISTER"}
VARIANTE = {"México": "MX", "Colombia": "CO", "Argentina": "AR"}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


# --- Gold -----------------------------------------------------------------------------------------

def cargar_gold():
    con = duckdb.connect(str(ROOT / "data" / "gold" / "gold.duckdb"), read_only=True)
    cols = ["transaction_id", "customer_id", "business_date", "amount", "currency", "merchant_name", "status"]
    txs = {r[0]: dict(zip(cols, r)) for r in con.execute(f"SELECT {', '.join(cols)} FROM dispute_transactions").fetchall()}
    clientes = {r[0]: dict(segment=r[1], country=r[2], prior=r[3]) for r in con.execute(
        "SELECT customer_id, segment, country, prior_complaints_90d FROM customer_profile").fetchall()}
    por_cliente = defaultdict(list)
    for t in txs.values():
        por_cliente[t["customer_id"]].append(t)
    return txs, clientes, por_cliente


def candidatas(filas: list[dict], monto=None, com=None, fecha=None) -> list[dict]:
    p = politica()
    hoy = date.fromisoformat(str(p["reference_date"]))
    lo = hoy - timedelta(days=p["search"]["lookback_days"])
    tol = p["search"]["amount_tolerance_pct"] / 100
    out = [t for t in filas if lo <= t["business_date"] <= hoy]
    if monto is not None:
        out = [t for t in out if abs(t["amount"] - monto) <= monto * tol]
    if com:
        out = [t for t in out if t["merchant_name"] and _norm(com) in _norm(t["merchant_name"])]
    if fecha:
        d1, d2 = (date.fromisoformat(x) for x in fecha)
        out = [t for t in out if d1 <= t["business_date"] <= d2]
    return out


# --- Referencias para la similitud ----------------------------------------------------------------

def frases_referencia() -> list[str]:
    textos: set[str] = set()
    intent = ROOT / "ml" / "intent"
    for f in (intent / "data").glob("*.jsonl"):
        for linea in f.open(encoding="utf-8"):
            textos.add(json.loads(linea)["text"])
    columnas = {"text", "text_limpio", "text_con_ruido", "semilla", "parafrasis_1", "parafrasis_2", "parafrasis_3",
                "ejemplo_1", "ejemplo_2", "ejemplo_3"}
    for f in list(intent.glob("*.csv")) + list((intent / "data").glob("*.csv")):
        with f.open(encoding="utf-8") as fh:
            for fila in csv.DictReader(fh):
                textos.update(v for k, v in fila.items() if k in columnas and v)
    for linea in (ROOT / "ml" / "llm" / "extraccion_casos.jsonl").open(encoding="utf-8"):
        textos.add(json.loads(linea)["text"])
    return sorted(t for t in textos if t and t.strip())


def similitud_max(mensajes: list[str], refs: list[str]) -> list[tuple[float, str]]:
    """Máximo coseno de cada mensaje contra las referencias, con dos vectorizadores; devuelve el mayor."""
    mejor = [(0.0, "")] * len(mensajes)
    for kw in (dict(analyzer="word", ngram_range=(1, 2)), dict(analyzer="char_wb", ngram_range=(3, 5))):
        vec = TfidfVectorizer(lowercase=True, strip_accents="unicode", **kw).fit(refs + mensajes)
        sim = cosine_similarity(vec.transform(mensajes), vec.transform(refs))
        for i, fila in enumerate(sim):
            j = int(fila.argmax())
            if fila[j] > mejor[i][0]:
                mejor[i] = (float(fila[j]), refs[j])
    return mejor


# --- Principal ------------------------------------------------------------------------------------

def main() -> int:
    txs, clientes, por_cliente = cargar_gold()
    errores: list[str] = []
    avisos: list[str] = []
    k = politica()["rules"]["repeat_disputes_k"]
    metas = {c["transaction_id"] for c in CASOS if c["transaction_id"]}   # incluye las ajenas

    numero = Counter()
    filas = []
    retirados: list[str] = []
    for c in CASOS:
        numero[(c["split"], c["category"])] += 1
        cid = f"{c['split']}-{c['category']}-{numero[(c['split'], c['category'])]:03d}"
        if c.get("retirado"):   # quitado en la revisión: conserva el número, no sale
            retirados.append(cid)
            continue
        cat, tx_id = c["category"], c["transaction_id"]
        tx = txs.get(tx_id) if tx_id else None
        if tx_id and tx is None:
            errores.append(f"{cid}: {tx_id} no existe en el gold")
            continue

        # cliente y dueño
        if cat == "acceso_no_autorizado":
            cli, owner = c["cli"], "other"
            if tx["customer_id"] == cli:
                errores.append(f"{cid}: la transacción ajena es del mismo cliente")
        elif tx is not None:
            cli, owner = tx["customer_id"], "self"
            if c.get("cli") and c["cli"] != cli:
                errores.append(f"{cid}: cli={c['cli']} pero la transacción es de {cli}")
        else:
            cli, owner = c["cli"], None
        perfil = clientes[cli]

        # guion
        script = []
        for turno in c["guion"]:
            if isinstance(turno, str):
                script.append({"kind": "message", "text": turno, "language": c["language"]})
            elif turno[0] == "ui":
                script.append({"kind": "ui_action", "type": "select_transaction", "transaction_id": turno[1]})
            else:
                script.append({"kind": "message", "text": turno[1], "language": turno[0]})
        idiomas = {t["language"] for t in script if t["kind"] == "message"}
        if c["language"] == "mix" and idiomas != {"es", "pt"} and cat != "multilingue":
            errores.append(f"{cid}: mix sin los dos idiomas")
        if c["language"] != "mix" and idiomas != {c["language"]}:
            errores.append(f"{cid}: idioma {c['language']} pero mensajes en {idiomas}")

        # identificación
        cita = {x: c.get(x) for x in ("monto", "com", "fecha")}
        n_cand = None
        if tx is not None and owner == "self":
            if cita["monto"] is not None and abs(tx["amount"] - cita["monto"]) > cita["monto"] * 0.02:
                errores.append(f"{cid}: monto citado {cita['monto']} lejos del real {tx['amount']}")
            if cita["com"] and not (tx["merchant_name"] and _norm(cita["com"]) in _norm(tx["merchant_name"])):
                errores.append(f"{cid}: comercio citado {cita['com']!r} ≠ {tx['merchant_name']!r}")
            if cita["fecha"] and not (date.fromisoformat(cita["fecha"][0]) <= tx["business_date"]
                                      <= date.fromisoformat(cita["fecha"][1])):
                errores.append(f"{cid}: fecha {cita['fecha']} no incluye {tx['business_date']}")
            cand = candidatas(por_cliente[cli], **cita)
            n_cand = len(cand)
            if [t["transaction_id"] for t in cand] != [tx_id]:
                errores.append(f"{cid}: con {cita} hay {n_cand} candidatas "
                               f"({[t['transaction_id'] for t in cand]}), se esperaba solo la meta")
            if "amb" in c:
                cand1 = candidatas(por_cliente[cli], **c["amb"])
                if len(cand1) < 2 or tx_id not in {t["transaction_id"] for t in cand1}:
                    errores.append(f"{cid}: el primer mensaje deja {len(cand1)} candidatas (se esperaban ≥ 2 con la meta)")
        if cat == "datos_incorrectos":
            if candidatas(por_cliente[cli], monto=cita["monto"]):
                errores.append(f"{cid}: el monto {cita['monto']} sí existe para {cli}")
            if any(t["merchant_name"] and _norm(cita["com"]) in _norm(t["merchant_name"]) for t in por_cliente[cli]):
                errores.append(f"{cid}: {cli} sí usó {cita['com']}")

        # preparación y regla esperada
        intencion = c.get("intencion", "cargo_no_reconocido")
        open_cases = []
        if c.get("prep") == "R5":
            open_cases = [tx_id]
        elif c.get("prep") == "R11":
            faltan = k - perfil["prior"]
            otras = sorted((t for t in por_cliente[cli] if t["transaction_id"] != tx_id
                            and t["transaction_id"] not in metas),
                           key=lambda t: (t["business_date"], t["transaction_id"]))
            open_cases = [t["transaction_id"] for t in otras[:faltan]]
            if len(open_cases) < faltan:
                errores.append(f"{cid}: no hay {faltan} transacciones libres para preparar R11")
        if cat in ("fuera_de_alcance", "datos_incorrectos"):
            regla = None
        else:
            regla = esperado(cli, tx_id, intencion, casos_previos=[CasoPrevio(t) for t in open_cases]).rule_id
        if regla not in REGLAS_OK[cat]:
            errores.append(f"{cid}: regla {regla} no encaja con la categoría {cat}")
        if intencion == "tarjeta_comprometida" and regla not in (None, "R1", "R7") and not tarjeta_activa(tx_id):
            errores.append(f"{cid}: tarjeta_comprometida con {regla} pero la tarjeta no está Active: no se propone el bloqueo")
        if c.get("bloqueo") and (intencion != "tarjeta_comprometida" or regla == "R7"):
            errores.append(f"{cid}: bloqueo= solo aplica a tarjeta_comprometida fuera de R7")
        if cat == "falla_herramienta" and {"block_card": "R7", "create_dispute_case": "R12"}[c["herramienta"]] != regla:
            errores.append(f"{cid}: herramienta {c['herramienta']} con regla {regla}")
        accion = "ABSTAIN" if cat == "fuera_de_alcance" else ("NOT_FOUND" if cat == "datos_incorrectos" else ACCION[regla])

        variante = {"es": VARIANTE[perfil["country"]], "pt": "BR",
                    "mix": f"{VARIANTE[perfil['country']]}+BR"}[c["language"]]
        extra = {x: c[x] for x in ("tema", "tipo_iny", "via", "error", "forma", "herramienta", "bloqueo") if x in c}
        filas.append(dict(
            id=cid, split=c["split"], category=cat, language=c["language"], variant=variante,
            customer_id=cli, segment=perfil["segment"], country=perfil["country"],
            transaction_id=tx_id, transaction_owner=owner, intencion=intencion,
            script=script, cita={x: v for x, v in cita.items() if v is not None},
            cita_primer_mensaje=c.get("amb"), candidatas=n_cand,
            open_cases_sugeridos=open_cases, expected_rule=regla, expected_action=accion,
            forbidden_markers=c.get("markers", []), message_author=c.get("autor", "claude"),
            seed_of=c.get("seed_of"), notes=c.get("nota"), **extra,
        ))

    # transacciones entre splits y usos
    uso = defaultdict(Counter)
    for f in filas:
        if f["transaction_id"]:
            uso[f["transaction_id"]][f["split"]] += 1
    for tx_id, u in uso.items():
        if len(u) > 1:
            errores.append(f"{tx_id} está en dev y en held-out")
        if u["heldout"] > 2:
            errores.append(f"{tx_id} se usa {u['heldout']} veces en held-out (máx. 2)")
        if u["dev"] > 3:
            avisos.append(f"{tx_id} se usa {u['dev']} veces en dev")
    prep = {t for f in filas for t in f["open_cases_sugeridos"] if f["expected_rule"] == "R11"}
    if prep & set(uso):
        errores.append(f"transacciones de preparación R11 que también son meta: {prep & set(uso)}")

    # similitud
    refs = frases_referencia()
    textos = [(f["id"], i, t["text"]) for f in filas for i, t in enumerate(f["script"]) if t["kind"] == "message"]
    sims = similitud_max([t for _, _, t in textos], refs)
    sim_por_caso: dict[str, float] = defaultdict(float)
    for (cid, i, texto), (s, ref) in zip(textos, sims):
        sim_por_caso[cid] = max(sim_por_caso[cid], s)
        if s > UMBRAL_SIM:
            errores.append(f"{cid} msg {i}: similitud {s:.2f} con {ref!r}")
    split_de = {f["id"]: f["split"] for f in filas}
    por_texto = defaultdict(set)
    for cid, _, texto in textos:
        por_texto[_norm(texto)].add(split_de[cid])
    for texto, splits in por_texto.items():
        if len(splits) > 1:
            errores.append(f"mensaje repetido en dev y held-out: {texto!r}")
    for f in filas:
        f["sim_max"] = round(sim_por_caso[f["id"]], 3)

    # salida
    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False, default=str) + "\n")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "categoria", "idioma", "mensaje", "transaccion", "regla_esperada",
                    "split", "variante", "cliente", "segmento", "dato_gold", "candidatas", "preparacion",
                    "sim_max", "nota"])
        for f in filas:
            msg = " ⏎ ".join(f"[{t['language']}] {t['text']}" if t["kind"] == "message"
                             else f"[ui_action select_transaction {t['transaction_id']}]" for t in f["script"])
            t = txs.get(f["transaction_id"]) if f["transaction_id"] else None
            dato = (f"{t['amount']:,.2f} {t['currency']} · {t['merchant_name'] or '(sin comercio)'} · "
                    f"{t['business_date']} · {t['status']}" + (f" · de {t['customer_id']}" if f["transaction_owner"] == "other" else "")
                    ) if t else ""
            prep_txt = (f"{f['expected_rule']}: casos abiertos en {', '.join(f['open_cases_sugeridos'])}"
                        if f["open_cases_sugeridos"] else "")
            nota = "; ".join(str(x) for x in (f.get("tema"), f.get("tipo_iny"), f.get("via"), f.get("error"),
                                               f.get("forma"), f.get("herramienta"), f.get("bloqueo"), f["notes"]) if x)
            w.writerow([f["id"], f["category"], f["language"], msg, f["transaction_id"] or "",
                        f["expected_rule"] or f["expected_action"], f["split"], f["variant"], f["customer_id"],
                        f["segment"], dato, f["candidatas"] if f["candidatas"] is not None else "", prep_txt,
                        f["sim_max"], nota])

    # resumen
    print(f"{len(filas)} casos → {OUT_JSONL.relative_to(ROOT)} y {OUT_CSV.relative_to(ROOT)}")
    print(f"retirados en la revisión ({len(retirados)}): {', '.join(retirados)}")
    for split in ("dev", "heldout"):
        sub = [f for f in filas if f["split"] == split]
        print(f"\n{split}: {len(sub)}")
        print("  categoría:", dict(Counter(f["category"] for f in sub)))
        print("  idioma:   ", dict(Counter(f["language"] for f in sub)))
        print("  segmento: ", dict(Counter(f["segment"] for f in sub)))
        print("  regla:    ", dict(sorted(Counter(str(f["expected_rule"]) for f in sub).items())))
    tot = Counter(f["language"] for f in filas)
    print("\nidioma total:", {k2: f"{v} ({v / len(filas):.0%})" for k2, v in tot.items()})
    print("variante:", dict(Counter(f["variant"] for f in filas)))
    print(f"similitud máx.: {max(f['sim_max'] for f in filas):.3f} (umbral {UMBRAL_SIM}); "
          f"referencias: {len(refs)} frases")
    for a in avisos:
        print("AVISO:", a)
    for e in errores:
        print("ERROR:", e)
    print(f"\n{len(errores)} errores")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
