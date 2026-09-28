"""Contratos de datos (Fase 2, rol A). Primeros esquemas: transactions y products.

Dominios tomados de los datos reales (transactions_12m, products). Se amplían en
docs/data_contracts.md. Un fallo de estos esquemas en silver es falla DURA.
"""
import pandera.pandas as pa
from pandera.pandas import Check, Column

TRANSACTION_STATUS = ["Approved", "Declined", "Pending", "Reversed"]
TRANSACTION_TYPES = ["Purchase", "Withdrawal", "Transfer", "Payment", "Deposit", "Adjustment"]
CHANNELS = ["POS", "ATM", "App", "Web", "Branch", "Transfer"]
CURRENCIES = ["ARS", "COP", "USD"]  # no hay MXN: los clientes de México operan en USD

transactions_silver = pa.DataFrameSchema(
    {
        "transaction_id": Column(str, unique=True, nullable=False),
        "transaction_ts_utc": Column("datetime64[ns, UTC]", nullable=False),
        "business_date": Column("datetime64[ns]", nullable=False),  # = process_date (partición)
        "customer_id": Column(str, nullable=False),
        "product_id": Column(str, nullable=False),
        "transaction_type": Column(str, Check.isin(TRANSACTION_TYPES)),
        "amount": Column(float, Check.gt(0)),
        "currency": Column(str, Check.isin(CURRENCIES)),
        "amount_usd": Column(float, Check.ge(0), nullable=False),  # USD: = amount (100 % nulo en origen); ARS/COP: ~5 % nulo → daily_exchange_rates
        "channel": Column(str, Check.isin(CHANNELS)),
        "merchant_name": Column(str, nullable=True),  # ~77 % nulo, esperado
        "transaction_country": Column(str, nullable=True),  # normalizar "Mexico" → "México"
        "transaction_status": Column(str, Check.isin(TRANSACTION_STATUS)),
        "fraud_score": Column(float, Check.in_range(0, 100), nullable=True),  # ~20 % nulo, esperado
        "is_fraud": Column(bool, nullable=False),
    },
    strict=False,
    coerce=True,
)

PRODUCT_STATUS = ["Active", "Closed", "Blocked", "Suspended"]
CARD_TYPES = ["Tarjeta Crédito", "Tarjeta Débito"]

products_silver = pa.DataFrameSchema(
    {
        "product_id": Column(str, unique=True, nullable=False),
        "customer_id": Column(str, nullable=False),
        "product_type": Column(str, nullable=False),
        "product_number": Column(str, nullable=True),  # sensible: solo sale a gold como card_mask
        "currency": Column(str, Check.isin(CURRENCIES)),
        "product_status": Column(str, Check.isin(PRODUCT_STATUS)),
    },
    strict=False,
    coerce=True,
)
