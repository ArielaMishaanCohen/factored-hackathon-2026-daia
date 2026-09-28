"""Herramientas de lectura de transacciones (design.md 4.3).

STUB de Fase 1 sobre stub_data. Fase 3 (C): consultar gold.dispute_transactions
en DuckDB con el filtro `customer_id = ?` DENTRO de la consulta.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..config import get_policy
from ..schemas import Session, ToolError, TransactionRisk, TransactionView
from . import stub_data

_CARD_MASK = {c["product_id"]: c["card_mask"] for c in stub_data.CARDS}


def _own_rows(session: Session) -> list[dict]:
    return [t for t in stub_data.TRANSACTIONS if t["customer_id"] == session.customer_id]


def _view(row: dict) -> TransactionView:
    return TransactionView(card_mask=_CARD_MASK.get(row["product_id"]),
                           **{k: row[k] for k in TransactionView.model_fields if k in row})


def search_transactions(session: Session, amount: float | None = None, currency: str | None = None,
                        date_from: date | None = None, date_to: date | None = None,
                        merchant: str | None = None) -> list[TransactionView]:
    policy = get_policy()
    ref = date.fromisoformat(policy["reference_date"])
    lo = max(date_from or date.min, ref - timedelta(days=policy["search"]["lookback_days"]))
    hi = min(date_to or date.max, ref)
    tol = policy["search"]["amount_tolerance_pct"] / 100

    rows = [r for r in _own_rows(session) if lo <= r["business_date"] <= hi]
    if currency:
        rows = [r for r in rows if r["currency"] == currency]
    if merchant:
        rows = [r for r in rows if r["merchant_name"] and merchant.lower() in r["merchant_name"].lower()]
    if amount is not None:
        rows = [r for r in rows if abs(r["amount"] - amount) <= amount * tol]
        rows.sort(key=lambda r: (abs(r["amount"] - amount), -r["business_date"].toordinal()))
    else:
        rows.sort(key=lambda r: r["business_date"], reverse=True)
    return [_view(r) for r in rows[: policy["search"]["max_results"]]]


def _get_row(session: Session, transaction_id: str) -> dict:
    for r in _own_rows(session):
        if r["transaction_id"] == transaction_id:
            return r
    raise ToolError("NOT_FOUND", "Transacción no encontrada.")  # igual si existe pero es de otro cliente


def get_transaction(session: Session, transaction_id: str) -> TransactionView:
    return _view(_get_row(session, transaction_id))


def get_transaction_risk(session: Session, transaction_id: str) -> TransactionRisk:
    r = _get_row(session, transaction_id)
    return TransactionRisk(transaction_id=transaction_id, amount_usd=r["amount_usd"], fraud_score=r["fraud_score"])
