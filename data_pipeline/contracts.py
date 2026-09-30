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

# Minimal required columns for each input file. Extra columns are retained in silver.
REQUIRED = {
    'transactions': ['transaction_id', 'transaction_date', 'process_date', 'customer_id',
                     'product_id', 'transaction_type', 'amount', 'currency', 'amount_usd',
                     'channel', 'merchant_name', 'transaction_country', 'transaction_status',
                     'fraud_score', 'is_fraud'],
    'products': ['product_id', 'customer_id', 'product_type', 'product_number', 'currency', 'product_status', 'last_updated'],
    'customers': ['customer_id', 'segment', 'country', 'last_updated'],
    'daily_exchange_rates': ['date', 'source_currency', 'target_currency', 'exchange_rate'],
    'complaints': ['complaint_id', 'customer_id', 'process_date', 'creation_date', 'subcategory', 'status', 'sla_breached', 'resolution_days'],
    'call_center_interactions': ['interaction_id', 'customer_id', 'process_date', 'interaction_date', 'reason_category', 'was_resolved', 'duration_seconds'],
    'satisfaction_surveys': ['survey_id', 'customer_id', 'interaction_id', 'process_date', 'survey_date', 'survey_type', 'main_score'],
    'service_agents': ['agent_id', 'languages', 'agent_status'],
}
PRIMARY_KEYS = {
    'transactions': ['transaction_id'], 'products': ['product_id'], 'customers': ['customer_id'],
    'daily_exchange_rates': ['date', 'source_currency', 'target_currency'],
    'complaints': ['complaint_id'], 'call_center_interactions': ['interaction_id'],
    'satisfaction_surveys': ['survey_id'], 'service_agents': ['agent_id'],
}


def schema_for(table):
    if table == 'transactions':
        return transactions_silver
    if table == 'products':
        return products_silver
    columns = {k: Column(str, nullable=False) for k in PRIMARY_KEYS[table]}
    if table == 'customers':
        columns.update(segment=Column(str, Check.isin(['Premium', 'Plus', 'Basic', 'Student'])), country=Column(str))
    elif table == 'daily_exchange_rates':
        columns.update(date=Column('datetime64[ns]'), exchange_rate=Column(float, Check.gt(0)))
    elif table == 'complaints':
        columns.update(customer_id=Column(str), business_date=Column('datetime64[ns]'),
                       subcategory=Column(str, nullable=True), status=Column(str, Check.isin(
                           ['Open', 'In Process', 'Escalated', 'Resolved', 'Closed', 'Rejected'])),
                       sla_breached=Column(bool), resolution_days=Column(float, Check.ge(0), nullable=True))
    elif table == 'call_center_interactions':
        columns.update(customer_id=Column(str), business_date=Column('datetime64[ns]'),
                       reason_category=Column(str), was_resolved=Column('boolean', nullable=True),
                       duration_seconds=Column(float, Check.ge(0), nullable=True))
    elif table == 'satisfaction_surveys':
        columns.update(customer_id=Column(str), business_date=Column('datetime64[ns]'),
                       survey_type=Column(str, Check.isin(['CSAT', 'NPS', 'CES'])),
                       main_score=Column(float, Check.in_range(0, 10)))
    elif table == 'service_agents':
        columns.update(languages=Column(str), agent_status=Column(str))
    return pa.DataFrameSchema(columns, strict=False, coerce=True)
