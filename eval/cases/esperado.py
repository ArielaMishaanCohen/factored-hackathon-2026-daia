"""Esperado de la política, derivado con código propio (Fase 6.1, Paso 4).

Dada una transacción, un cliente y una intención, devuelve la primera regla de
docs/design.md §3.2 que aplica (R0 a R12, en ese orden), con su acción, prioridad,
cola y si se crea caso.

A propósito, NO importa nada de backend/: los umbrales se leen de config/policy.yaml y
los datos del gold se consultan con SQL propio. Si el motor del backend tiene un bug,
este script no lo copia; las diferencias se resuelven a mano antes de construir el set.

Lo que no está en el gold (sesión, casos ya abiertos) entra como parámetro: es la
«preparación» del caso (SCHEMA.md, `setup`).

Uso:
    python -m eval.cases.esperado CLI-XXXX TX-YYYY [intencion]
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "gold" / "gold.duckdb"
POLICY = ROOT / "config" / "policy.yaml"

# Estados de caso que cuentan como «caso abierto» para R5. design.md no los enumera:
# se toman los que aún no tienen resolución (Resolved, Closed y Rejected la tienen).
ESTADOS_ABIERTOS = {"Open", "In Process", "Escalated"}


@dataclass(frozen=True)
class Esperado:
    rule_id: str
    action: str
    priority: str | None
    queue: str | None
    crea_caso: bool          # si el cliente confirma; sin confirmación, R6–R12 terminan en handoff sin caso


@dataclass(frozen=True)
class CasoPrevio:
    """Caso que ya existe en el SQLite operativo (setup.open_cases). Se asume creado «hoy»."""
    transaction_id: str
    status: str = "Open"


@lru_cache(maxsize=1)
def politica() -> dict:
    with open(POLICY, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(GOLD), read_only=True)


def _fila(sql: str, params: list) -> dict | None:
    cur = _con().cursor()
    try:
        rel = cur.execute(sql, params)
        cols = [d[0] for d in rel.description]
        row = rel.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        cur.close()


def transaccion_gold(transaction_id: str) -> dict | None:
    """La transacción SIN filtrar por cliente: R1 se decide aquí, comparando customer_id."""
    return _fila("""
        SELECT transaction_id, customer_id, business_date, amount_usd, transaction_type,
               status, fraud_score
        FROM dispute_transactions WHERE transaction_id = ?
    """, [transaction_id])


def tarjeta_activa(transaction_id: str) -> bool:
    """Si la tarjeta de la transacción está Active en el gold. Con tarjeta_comprometida fuera de R7, el
    bloqueo solo se propone si lo está (design.md §3.2): una tarjeta ya bloqueada no se vuelve a ofrecer."""
    fila = _fila("""
        SELECT c.status FROM dispute_transactions t JOIN cards c ON c.product_id = t.product_id
        WHERE t.transaction_id = ?
    """, [transaction_id])
    return bool(fila) and fila["status"] == "Active"


def quejas_90d(customer_id: str) -> int:
    fila = _fila("SELECT prior_complaints_90d FROM customer_profile WHERE customer_id = ?", [customer_id])
    return int(fila["prior_complaints_90d"] or 0) if fila else 0


def esperado(customer_id: str, transaction_id: str, intencion: str, *,
             casos_previos: list[CasoPrevio] | None = None, sesion_valida: bool = True) -> Esperado:
    p = politica()
    r = p["rules"]
    casos = casos_previos or []

    # R0: sesión inválida o expirada, antes de mirar cualquier dato.
    if not sesion_valida:
        return Esperado("R0", "REAUTH", None, None, False)

    # R1: la transacción no existe o es de otro cliente (mismo resultado en ambos casos).
    tx = transaccion_gold(transaction_id)
    if tx is None or tx["customer_id"] != customer_id:
        return Esperado("R1", "NOT_FOUND", None, None, False)

    # R2–R4: el estado dice que no hay nada que disputar.
    estado = tx["status"]
    if estado == "Declined":
        return Esperado("R2", "INFORM", None, None, False)
    if estado == "Pending":
        return Esperado("R3", "INFORM", None, None, False)
    if estado == "Reversed":
        return Esperado("R4", "INFORM", None, None, False)

    # R5: ya hay un caso abierto para esta transacción.
    if any(c.transaction_id == transaction_id and c.status in ESTADOS_ABIERTOS for c in casos):
        return Esperado("R5", "INFORM", None, None, False)

    # R6: más vieja que τ_ventana días respecto de la fecha de referencia.
    hoy = date.fromisoformat(str(p["reference_date"]))
    if tx["business_date"] < hoy - timedelta(days=r["claim_window_days"]):
        return Esperado("R6", "ESCALATE", "medium", "disputas", True)

    # R7: tarjeta comprometida o score ≥ τ_alto.
    score = tx["fraud_score"]
    if intencion == "tarjeta_comprometida" or (score is not None and score >= r["fraud_score_high"]):
        return Esperado("R7", "FRAUD", "critical", "fraude", True)

    # R8: score nulo.
    if score is None:
        return Esperado("R8", "ESCALATE", "high", "disputas", True)

    # R9: zona gris [τ_bajo, τ_alto).
    if r["fraud_score_low"] <= score < r["fraud_score_high"]:
        return Esperado("R9", "ESCALATE", "high", "fraude", True)

    # R10: monto alto para su tipo.
    topes = r["amount_usd_max"]
    if tx["amount_usd"] > topes.get(tx["transaction_type"], topes["default"]):
        return Esperado("R10", "ESCALATE", "high", "disputas", True)

    # R11: ≥ τ_k disputas en la ventana, en cualquier estado (design.md §3.2): quejas del gold + casos
    # de la preparación (se asumen creados hoy, dentro de repeat_window_days; Closed también cuenta).
    if quejas_90d(customer_id) + len(casos) >= r["repeat_disputes_k"]:
        return Esperado("R11", "ESCALATE", "medium", "disputas", True)

    # R12: nada de lo anterior.
    return Esperado("R12", "AUTO_REGISTER", "medium", None, True)


if __name__ == "__main__":
    cli, tx_id, *resto = sys.argv[1:]
    print(asdict(esperado(cli, tx_id, resto[0] if resto else "cargo_no_reconocido")))
