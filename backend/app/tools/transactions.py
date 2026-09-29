"""Herramientas de lectura de transacciones (design.md 4.3).

Los datos salen de data_source: gold.duckdb si existe, o los stubs si no.
El filtro por cliente vive en la consulta (data_source), no aquí ni en el orquestador.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..config import get_policy
from ..faults import inject
from ..schemas import Session, ToolError, TransactionRisk, TransactionView
from . import data_source


def _view(row: dict) -> TransactionView:
    return TransactionView(**{k: row.get(k) for k in TransactionView.model_fields})


def search_transactions(session: Session, amount: float | None = None, currency: str | None = None,
                        date_from: date | None = None, date_to: date | None = None,
                        merchant: str | None = None) -> list[TransactionView]:
    inject("search_transactions")
    policy = get_policy()
    ref = date.fromisoformat(policy["reference_date"])
    lo = max(date_from or date.min, ref - timedelta(days=policy["search"]["lookback_days"]))
    hi = min(date_to or date.max, ref)
    tol = policy["search"]["amount_tolerance_pct"] / 100

    rows = data_source.transactions_between(session.customer_id, lo, hi)
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
    row = data_source.transaction(session.customer_id, transaction_id)
    if row is not None:
        return row
    raise ToolError("NOT_FOUND", "Transacción no encontrada.")  # igual si existe pero es de otro cliente


def get_transaction(session: Session, transaction_id: str) -> TransactionView:
    inject("get_transaction")
    return _view(_get_row(session, transaction_id))


def get_transaction_risk(session: Session, transaction_id: str) -> TransactionRisk:
    inject("get_transaction_risk")
    r = _get_row(session, transaction_id)
    return TransactionRisk(transaction_id=transaction_id, amount_usd=r["amount_usd"], fraud_score=r["fraud_score"])
