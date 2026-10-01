"""Muestra de revisión de los esperados del held-out (Fase 6.1, Paso 8).

40 casos estratificados por categoría (al menos 2 por categoría; el resto en proporción al
tamaño de cada una) y, dentro de cada categoría, rotando entre reglas esperadas para que
salgan todas las que hay. Por cada caso: los datos del gold de la transacción y la consulta
que justifica el esperado. NO corre el sistema ni lee nada de backend/.

Uso:
    python -m eval.cases.muestra_revision      # escribe eval/cases/revision_esperados.csv
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

from eval.cases.esperado import CasoPrevio, esperado, politica, quejas_90d, transaccion_gold

AQUI = Path(__file__).resolve().parent
HELDOUT = AQUI / "heldout.jsonl"
SALIDA = AQUI / "revision_esperados.csv"
N, MINIMO, SEMILLA = 40, 2, 61

SQL_TX = ("SELECT customer_id, business_date, amount_usd, transaction_type, status, fraud_score "
          "FROM dispute_transactions WHERE transaction_id = '{tx}'")
SQL_QUEJAS = "SELECT prior_complaints_90d FROM customer_profile WHERE customer_id = '{cli}'"
SQL_CANDIDATAS = ("SELECT * FROM dispute_transactions WHERE customer_id = '{cli}' "
                  "AND business_date BETWEEN DATE '{ref}' - {lookback} AND DATE '{ref}'{filtros}")

COLUMNAS = ["case_id", "categoria", "cliente", "segmento", "mensaje", "transaction_id", "dueno_tx", "status",
            "fraud_score", "amount_usd", "transaction_type", "dias_desde_tx", "rule_id_esperado", "accion",
            "prioridad", "cola", "tarjeta_bloqueada", "consulta_gold", "por_que", "notas"]


def asignacion(por_cat: dict[str, list]) -> dict[str, int]:
    """MINIMO por categoría y el resto por restos mayores, proporcional a lo que queda en cada una."""
    cupo = {c: min(MINIMO, len(v)) for c, v in por_cat.items()}
    resto = N - sum(cupo.values())
    sobrante = {c: len(v) - cupo[c] for c, v in por_cat.items()}
    total = sum(sobrante.values())
    exacto = {c: resto * s / total for c, s in sobrante.items()}
    for c in cupo:
        cupo[c] += int(exacto[c])
    faltan = N - sum(cupo.values())
    for c in sorted(exacto, key=lambda c: (-(exacto[c] - int(exacto[c])), c))[:faltan]:
        cupo[c] += 1
    return cupo


def _intencion(c: dict) -> str | None:
    gq = c["provenance"]["gold_query"]
    return gq["params"].get("intencion") if gq else None


def estrato(c: dict) -> str:
    """Regla esperada; tarjeta comprometida fuera de R7 (bloqueo antes de la regla) va aparte."""
    regla = str(c["expected"]["rule_id"])
    return regla + "+tarjeta" if _intencion(c) == "tarjeta_comprometida" and regla != "R7" else regla


def elegir(casos: list[dict], k: int, rng: random.Random) -> list[dict]:
    """Rota entre estratos (del más raro al más común) para cubrirlos todos."""
    por_regla: dict[str, list] = defaultdict(list)
    for c in casos:
        por_regla[estrato(c)].append(c)
    colas = [rng.sample(v, len(v)) for _, v in sorted(por_regla.items(), key=lambda kv: (len(kv[1]), kv[0]))]
    out: list[dict] = []
    while len(out) < k:
        for cola in colas:
            if cola and len(out) < k:
                out.append(cola.pop())
    return sorted(out, key=lambda c: c["case_id"])


def por_que(c: dict, tx: dict | None, quejas: int, intencion: str | None) -> str:
    p = politica()["rules"]
    e, s = c["expected"], c["setup"]
    regla = e["rule_id"]
    if regla is None:
        return "fuera de alcance: sin transacción ni regla (esperado manual)" if not e["in_scope"] \
            else "0 candidatas en el gold → NOT_FOUND y handoff NO_TRANSACTION_FOUND"
    if regla == "R1":
        return f"la transacción es de {tx['customer_id']}, no del cliente" if tx else "la transacción no existe"
    textos = {
        "R2": "status = Declined", "R3": "status = Pending", "R4": "status = Reversed",
        "R5": (f"status = {tx['status']} y la preparación ya tiene caso abierto: "
               + ", ".join(f"{o['transaction_id']} ({o.get('status', 'Open')})" for o in s["open_cases"])),
        "R6": f"{c['_dias']} días > claim_window_days = {p['claim_window_days']}",
        "R7": (f"intención = tarjeta_comprometida (fraud_score {tx['fraud_score']})"
               if intencion == "tarjeta_comprometida"
               else f"fraud_score {tx['fraud_score']} ≥ fraud_score_high = {p['fraud_score_high']}"),
        "R8": "fraud_score nulo",
        "R9": f"fraud_score {tx['fraud_score']} en [{p['fraud_score_low']}, {p['fraud_score_high']})",
        "R10": (f"amount_usd {tx['amount_usd']} > tope de {tx['transaction_type']} = "
                f"{p['amount_usd_max'].get(tx['transaction_type'], p['amount_usd_max']['default'])}"),
        "R11": (f"quejas_90d {quejas} + casos previos {len(s['open_cases'])} ≥ "
                f"repeat_disputes_k = {p['repeat_disputes_k']}"),
        "R12": (f"status = {tx['status']}, {c['_dias']} días ≤ {p['claim_window_days']}, fraud_score {tx['fraud_score']} "
                f"< {p['fraud_score_low']}, monto bajo el tope, quejas_90d {quejas} + previos "
                f"{len(s['open_cases'])} < {p['repeat_disputes_k']}"),
    }
    texto = textos[regla]
    if intencion == "tarjeta_comprometida" and regla != "R7":
        confirma = c["response_rules"]["on_confirmation"]["block_card"] == "confirm"
        texto += (" · tarjeta comprometida: se propone bloquear la tarjeta de la transacción (Active en el gold); el cliente "
                  + ("confirma" if confirma else "cancela")
                  + (" → handoff a fraude sin caso" if e["action"] == "INFORM" else " → caso de la regla y handoff"
                     if confirma else " → handoff sin caso"))
    if s["faults"]:
        texto += f" · falla inyectada: {s['faults'][0]['tool']} en {s['faults'][0]['at']}"
    if s["expire_session"]:
        texto += f" · sesión expira antes de {s['expire_session']['before_turn']}"
    return texto


def consulta(c: dict, cli: str) -> str:
    gq = c["provenance"]["gold_query"]
    if gq is None:
        return ""
    pp = gq["params"]
    if gq["name"] == "verificar_mensajes.candidatas":
        pol = politica()
        filtros = ""
        if pp.get("monto") is not None:
            filtros += f" AND abs(amount - {pp['monto']}) <= {pp['monto']} * {pol['search']['amount_tolerance_pct'] / 100}"
        if pp.get("com"):  # sin tildes ni mayúsculas, como verificar_mensajes.candidatas
            filtros += f" AND strip_accents(lower(merchant_name)) LIKE '%' || strip_accents(lower('{pp['com']}')) || '%'"
        if pp.get("fecha"):
            filtros += f" AND business_date BETWEEN '{pp['fecha'][0]}' AND '{pp['fecha'][1]}'"
        return f"{gq['name']}({json.dumps(pp, ensure_ascii=False)}) ≡ " + SQL_CANDIDATAS.format(
            cli=cli, ref=pol["reference_date"], lookback=pol["search"]["lookback_days"], filtros=filtros)
    return (f"{gq['name']}({json.dumps(pp, ensure_ascii=False)}) ≡ " + SQL_TX.format(tx=pp["transaction_id"])
            + " ; " + SQL_QUEJAS.format(cli=cli))


def fila(c: dict) -> dict:
    e, cli = c["expected"], c["customer_id"]
    tx = transaccion_gold(e["transaction_id"]) if e["transaction_id"] else None
    hoy = date.fromisoformat(str(politica()["reference_date"]))
    c["_dias"] = (hoy - tx["business_date"]).days if tx else None
    quejas = quejas_90d(cli)

    # Prioridad y cola de la regla (esperado.py); el caso puede no crearse (falla, sesión) y dejarlas en null.
    prioridad, cola = e["case"]["priority"], e["case"]["queue"]
    gq = c["provenance"]["gold_query"]
    if gq and gq["name"] == "esperado.esperado":
        previos = [CasoPrevio(o["transaction_id"], o.get("status", "Open")) for o in c["setup"]["open_cases"]]
        esp = esperado(cli, e["transaction_id"], gq["params"]["intencion"], casos_previos=previos)
        assert esp.rule_id == e["rule_id"], (c["case_id"], esp.rule_id, e["rule_id"])
        prioridad, cola = prioridad or esp.priority, cola or esp.queue

    return {
        "case_id": c["case_id"], "categoria": c["category"], "cliente": cli, "segmento": c["segment"],
        "mensaje": " | ".join(f"[{t['language']}] {t['text']}" for t in c["script"] if t["kind"] == "message"),
        "transaction_id": e["transaction_id"] or "",
        "dueno_tx": (tx["customer_id"] if tx and tx["customer_id"] != cli else ("cliente" if tx else "")),
        "status": tx["status"] if tx else "", "fraud_score": "" if not tx or tx["fraud_score"] is None
        else tx["fraud_score"], "amount_usd": tx["amount_usd"] if tx else "",
        "transaction_type": tx["transaction_type"] if tx else "", "dias_desde_tx": c["_dias"] if tx else "",
        "rule_id_esperado": e["rule_id"] or "", "accion": e["action"], "prioridad": prioridad or "",
        "cola": cola or "", "tarjeta_bloqueada": "sí" if e["card_blocked"] else "",
        "consulta_gold": consulta(c, cli), "por_que": por_que(c, tx, quejas, _intencion(c)),
        "notas": c["provenance"]["notes"] or "",
    }


def main() -> None:
    casos = [json.loads(l) for l in HELDOUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    por_cat: dict[str, list] = defaultdict(list)
    for c in casos:
        por_cat[c["category"]].append(c)
    rng = random.Random(SEMILLA)
    cupo = asignacion(por_cat)
    muestra = [c for cat in sorted(por_cat) for c in elegir(por_cat[cat], cupo[cat], rng)]
    with SALIDA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(fila(c) for c in muestra)
    print(f"{len(muestra)} casos → {SALIDA.relative_to(AQUI.parents[1])}")
    for cat in sorted(cupo):
        print(f"  {cat:22s} {cupo[cat]:2d} / {len(por_cat[cat])}")


if __name__ == "__main__":
    main()
