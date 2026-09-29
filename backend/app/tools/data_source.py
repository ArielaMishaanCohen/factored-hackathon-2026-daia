"""De dónde salen los datos del banco: gold.duckdb (real) o stub_data (de plástico).

Regla: si existe el archivo GOLD_DB_PATH (data/gold/gold.duckdb), se usa SIEMPRE.
Si no existe, se usan los stubs, para poder desarrollar y hacer la demo sin él.

Seguridad (design.md 4.1): toda consulta de datos de un cliente lleva
`WHERE customer_id = ?` DENTRO del SQL. El filtro no depende del orquestador ni del LLM.
El `?` es un parámetro: DuckDB lo trata como dato, nunca como código (evita inyección SQL).
"""
from __future__ import annotations

import threading
from datetime import date

import duckdb

from ..config import get_settings
from . import stub_data

_TX_COLS = ("t.transaction_id, t.customer_id, t.product_id, t.business_date, t.amount, t.currency, "
            "t.amount_usd, t.merchant_name, t.transaction_type, t.channel, t.status, t.fraud_score, "
            "c.card_mask")

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None
_con_path = None


def using_gold() -> bool:
    return get_settings().gold_db_path.exists()


def source_name() -> str:
    return f"gold:{get_settings().gold_db_path.name}" if using_gold() else "stub"


def _query(sql: str, params: list | None = None) -> list[dict]:
    """Una conexión de solo lectura compartida; un cursor por consulta (seguro entre hilos)."""
    global _con, _con_path
    path = get_settings().gold_db_path
    with _lock:
        if _con is None or _con_path != path:
            _con = duckdb.connect(str(path), read_only=True)
            _con_path = path
        cur = _con.cursor()
    try:
        rel = cur.execute(sql, params or [])
        cols = [d[0] for d in rel.description]
        return [dict(zip(cols, row)) for row in rel.fetchall()]
    finally:
        cur.close()


def reset_connection() -> None:
    """Para tests: cerrar la conexión si cambia el archivo."""
    global _con, _con_path
    with _lock:
        if _con is not None:
            _con.close()
        _con, _con_path = None, None


# --- Transacciones ------------------------------------------------------------------

def _stub_tx(row: dict) -> dict:
    mask = next((c["card_mask"] for c in stub_data.CARDS if c["product_id"] == row["product_id"]), None)
    return {**row, "card_mask": mask}


def transactions_between(customer_id: str, lo: date, hi: date) -> list[dict]:
    """Transacciones DEL CLIENTE entre dos fechas (incluidas)."""
    if using_gold():
        return _query(f"""
            SELECT {_TX_COLS}
            FROM dispute_transactions t
            LEFT JOIN cards c ON c.product_id = t.product_id AND c.customer_id = t.customer_id
            WHERE t.customer_id = ? AND t.business_date BETWEEN ? AND ?
        """, [customer_id, lo, hi])
    return [_stub_tx(t) for t in stub_data.TRANSACTIONS
            if t["customer_id"] == customer_id and lo <= t["business_date"] <= hi]


def transaction(customer_id: str, transaction_id: str) -> dict | None:
    """Una transacción, solo si es DEL CLIENTE. Si es de otro, devuelve None (igual que si no existiera)."""
    if using_gold():
        rows = _query(f"""
            SELECT {_TX_COLS}
            FROM dispute_transactions t
            LEFT JOIN cards c ON c.product_id = t.product_id AND c.customer_id = t.customer_id
            WHERE t.customer_id = ? AND t.transaction_id = ?
        """, [customer_id, transaction_id])
        return rows[0] if rows else None
    return next((_stub_tx(t) for t in stub_data.TRANSACTIONS
                 if t["customer_id"] == customer_id and t["transaction_id"] == transaction_id), None)


# --- Tarjetas -----------------------------------------------------------------------

def card(customer_id: str, product_id: str) -> dict | None:
    if using_gold():
        rows = _query("SELECT product_id, customer_id, card_mask, status FROM cards "
                      "WHERE customer_id = ? AND product_id = ?", [customer_id, product_id])
        return rows[0] if rows else None
    return next((c for c in stub_data.CARDS
                 if c["customer_id"] == customer_id and c["product_id"] == product_id), None)


# --- Clientes -----------------------------------------------------------------------

def demo_customers() -> list[dict]:
    if using_gold():
        return _query("SELECT customer_id, display_name, segment, country, suggested_language, scenario "
                      "FROM demo_customers ORDER BY customer_id")
    return list(stub_data.DEMO_CUSTOMERS)


def customer_profile(customer_id: str) -> dict:
    """segment, country y prior_complaints_90d (para R11 y el handoff)."""
    if using_gold():
        rows = _query("SELECT segment, country, prior_complaints_90d FROM customer_profile "
                      "WHERE customer_id = ?", [customer_id])
        return rows[0] if rows else {"segment": "?", "country": "?", "prior_complaints_90d": 0}
    return dict(stub_data.CUSTOMER_PROFILE.get(customer_id,
                                               {"segment": "?", "country": "?", "prior_complaints_90d": 0}))
