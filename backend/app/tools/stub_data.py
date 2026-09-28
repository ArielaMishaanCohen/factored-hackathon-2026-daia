"""Datos falsos de Fase 1 con la forma de gold (design.md 4.5).

Fase 2/3: se reemplazan por las tablas de gold (DuckDB). Los IDs son inventados
y no corresponden a clientes del dataset.
"""
from datetime import date

DEMO_CUSTOMERS = [
    {"customer_id": "CUS-DEMO-01", "display_name": "Cliente demo 1", "segment": "Basic",
     "country": "México", "suggested_language": "es", "scenario": "Resolución normal"},
    {"customer_id": "CUS-DEMO-02", "display_name": "Cliente demo 2", "segment": "Plus",
     "country": "Colombia", "suggested_language": "es", "scenario": "Ambiguo (varias candidatas)"},
    {"customer_id": "CUS-DEMO-03", "display_name": "Cliente demo 3", "segment": "Premium",
     "country": "Argentina", "suggested_language": "pt", "scenario": "Fraude con bloqueo y handoff"},
]

CARDS = [
    {"product_id": "PRD-DEMO-01", "customer_id": "CUS-DEMO-01", "card_mask": "•••• 4821", "status": "Active"},
    {"product_id": "PRD-DEMO-02", "customer_id": "CUS-DEMO-02", "card_mask": "•••• 1093", "status": "Active"},
    {"product_id": "PRD-DEMO-03", "customer_id": "CUS-DEMO-03", "card_mask": "•••• 7750", "status": "Active"},
]

# Columnas de gold.dispute_transactions (incluye las internas amount_usd y fraud_score).
TRANSACTIONS = [
    {"transaction_id": "TX-DEMO-0001", "customer_id": "CUS-DEMO-01", "product_id": "PRD-DEMO-01",
     "business_date": date(2026, 6, 10), "amount": 350.0, "currency": "USD", "amount_usd": 350.0,
     "merchant_name": "OXXO", "transaction_type": "Purchase", "channel": "POS",
     "status": "Approved", "fraud_score": 12.0},
    {"transaction_id": "TX-DEMO-0002", "customer_id": "CUS-DEMO-01", "product_id": "PRD-DEMO-01",
     "business_date": date(2026, 6, 2), "amount": 89.9, "currency": "USD", "amount_usd": 89.9,
     "merchant_name": None, "transaction_type": "Purchase", "channel": "Web",
     "status": "Declined", "fraud_score": 5.0},
    {"transaction_id": "TX-DEMO-0003", "customer_id": "CUS-DEMO-02", "product_id": "PRD-DEMO-02",
     "business_date": date(2026, 6, 14), "amount": 120000.0, "currency": "COP", "amount_usd": 30.1,
     "merchant_name": "Éxito", "transaction_type": "Purchase", "channel": "POS",
     "status": "Approved", "fraud_score": 8.0},
    {"transaction_id": "TX-DEMO-0004", "customer_id": "CUS-DEMO-02", "product_id": "PRD-DEMO-02",
     "business_date": date(2026, 6, 14), "amount": 120000.0, "currency": "COP", "amount_usd": 30.1,
     "merchant_name": "Éxito", "transaction_type": "Purchase", "channel": "POS",
     "status": "Approved", "fraud_score": 9.0},
    {"transaction_id": "TX-DEMO-0005", "customer_id": "CUS-DEMO-02", "product_id": "PRD-DEMO-02",
     "business_date": date(2026, 6, 9), "amount": 45000.0, "currency": "COP", "amount_usd": 11.3,
     "merchant_name": None, "transaction_type": "Payment", "channel": "App",
     "status": "Approved", "fraud_score": None},
    {"transaction_id": "TX-DEMO-0006", "customer_id": "CUS-DEMO-03", "product_id": "PRD-DEMO-03",
     "business_date": date(2026, 6, 15), "amount": 3500.0, "currency": "USD", "amount_usd": 3500.0,
     "merchant_name": "Tienda online", "transaction_type": "Purchase", "channel": "Web",
     "status": "Approved", "fraud_score": 47.2},
]

CUSTOMER_PROFILE = {c["customer_id"]: {"segment": c["segment"], "country": c["country"],
                                        "prior_complaints_90d": 0} for c in DEMO_CUSTOMERS}
