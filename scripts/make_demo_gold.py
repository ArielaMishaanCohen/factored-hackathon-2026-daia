"""Crea un gold.duckdb DE PRUEBA a partir de los stubs, con el esquema del contrato (design.md 4.5).

Para qué sirve:
  1. Probar que el backend lee bien de DuckDB antes de que llegue el gold real.
  2. Mostrarle al rol A (datos) exactamente qué tablas, columnas y tipos espera el backend.

Uso:  python scripts/make_demo_gold.py [ruta_salida]
      (por defecto: data/gold/gold.duckdb)
OJO: si ya existe un gold real en esa ruta, NO lo pisa (usá otra ruta).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.tools import stub_data  # noqa: E402

SCHEMA = """
CREATE TABLE dispute_transactions (
    transaction_id   VARCHAR PRIMARY KEY,
    customer_id      VARCHAR NOT NULL,
    product_id       VARCHAR NOT NULL,
    business_date    DATE    NOT NULL,
    amount           DOUBLE  NOT NULL,
    currency         VARCHAR NOT NULL,     -- ARS | COP | USD
    amount_usd       DOUBLE  NOT NULL,     -- sin nulos (contrato de silver)
    merchant_name    VARCHAR,              -- puede ser nulo
    transaction_type VARCHAR NOT NULL,
    channel          VARCHAR NOT NULL,
    status           VARCHAR NOT NULL,     -- Approved | Declined | Pending | Reversed
    fraud_score      DOUBLE                -- puede ser nulo (~20 %): dispara R8
);
CREATE TABLE cards (
    product_id  VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    card_mask   VARCHAR,                   -- p. ej. '•••• 4821', nunca el número completo
    status      VARCHAR NOT NULL           -- Active | Blocked | Suspended | Closed
);
CREATE TABLE customer_profile (
    customer_id          VARCHAR PRIMARY KEY,
    segment              VARCHAR NOT NULL,
    country              VARCHAR NOT NULL,
    prior_complaints_90d INTEGER NOT NULL
);
CREATE TABLE demo_customers (
    customer_id        VARCHAR PRIMARY KEY,
    display_name       VARCHAR NOT NULL,   -- ficticio
    segment            VARCHAR NOT NULL,
    country            VARCHAR NOT NULL,
    suggested_language VARCHAR NOT NULL,   -- es | pt
    scenario           VARCHAR NOT NULL
);
"""


def build(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    con.execute(SCHEMA)
    tx_cols = ["transaction_id", "customer_id", "product_id", "business_date", "amount", "currency",
               "amount_usd", "merchant_name", "transaction_type", "channel", "status", "fraud_score"]
    con.executemany(f"INSERT INTO dispute_transactions VALUES ({', '.join('?' * len(tx_cols))})",
                    [[t[c] for c in tx_cols] for t in stub_data.TRANSACTIONS])
    con.executemany("INSERT INTO cards VALUES (?, ?, ?, ?)",
                    [[c["product_id"], c["customer_id"], c["card_mask"], c["status"]] for c in stub_data.CARDS])
    con.executemany("INSERT INTO customer_profile VALUES (?, ?, ?, ?)",
                    [[cid, p["segment"], p["country"], p["prior_complaints_90d"]]
                     for cid, p in stub_data.CUSTOMER_PROFILE.items()])
    con.executemany("INSERT INTO demo_customers VALUES (?, ?, ?, ?, ?, ?)",
                    [[c["customer_id"], c["display_name"], c["segment"], c["country"],
                      c["suggested_language"], c["scenario"]] for c in stub_data.DEMO_CUSTOMERS])
    con.close()
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "gold" / "gold.duckdb"
    if target.exists() and len(sys.argv) == 1:
        sys.exit(f"Ya existe {target}. Si es el gold real, no lo piso. Pasá otra ruta como argumento.")
    print(f"Gold de prueba creado en {build(target)}")
