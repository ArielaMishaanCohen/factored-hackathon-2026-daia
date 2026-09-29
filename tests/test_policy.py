"""Tests del motor de política: una prueba por regla y por cada BORDE.

El motor es una función pura, así que aquí NO usamos la API: armamos una transacción
de mentira, llamamos a evaluate() y revisamos qué regla eligió.
"""
from datetime import date

import pytest

from app.config import get_policy
from app.policy.engine import evaluate
from app.schemas import TransactionRisk, TransactionView

POLICY = get_policy()  # los mismos números que usa el sistema (config/policy.yaml)


def tx(status="Approved", days_ago=7, tx_type="Purchase"):
    """Una transacción 'normal' que, sin cambios, termina en R12."""
    ref = date.fromisoformat(POLICY["reference_date"])
    return TransactionView(
        transaction_id="TX-1", business_date=date.fromordinal(ref.toordinal() - days_ago),
        amount=100.0, currency="USD", merchant_name="Tienda", transaction_type=tx_type,
        channel="POS", status=status, product_id="PRD-1", card_mask="•••• 1234")


def risk(score=10.0, amount_usd=100.0):
    return TransactionRisk(transaction_id="TX-1", amount_usd=amount_usd, fraud_score=score)


def rule(t=None, r=None, ctx=None, intent="cargo_no_reconocido"):
    return evaluate(t or tx(), r or risk(), ctx or {}, intent, POLICY).rule_id


# --- Una prueba por regla -------------------------------------------------------------

def test_R12_caso_normal():
    assert rule() == "R12"


@pytest.mark.parametrize("status, esperado", [("Declined", "R2"), ("Pending", "R3"), ("Reversed", "R4")])
def test_R2_R3_R4_estado_de_la_transaccion(status, esperado):
    assert rule(t=tx(status=status)) == esperado


def test_R5_caso_abierto():
    ctx = {"open_cases_by_tx": {"TX-1": {"case_id": "DSP-000001", "status": "Open"}}}
    assert rule(ctx=ctx) == "R5"


def test_R6_fuera_de_ventana():
    assert rule(t=tx(days_ago=POLICY["rules"]["claim_window_days"] + 1)) == "R6"


def test_R7_por_score_alto():
    assert rule(r=risk(score=47.2)) == "R7"


def test_R7_por_intencion_tarjeta_comprometida():
    assert rule(intent="tarjeta_comprometida") == "R7"


def test_R8_score_nulo():
    assert rule(r=risk(score=None)) == "R8"


def test_R9_zona_gris():
    assert rule(r=risk(score=35)) == "R9"


def test_R10_monto_alto():
    limite = POLICY["rules"]["amount_usd_max"]["Purchase"]
    assert rule(r=risk(amount_usd=limite + 1)) == "R10"


def test_R11_cliente_con_muchas_disputas():
    assert rule(ctx={"prior_complaints_90d": POLICY["rules"]["repeat_disputes_k"]}) == "R11"


# --- Bordes: justo en el límite, ¿de qué lado cae? -----------------------------------

def test_borde_score_igual_a_tau_alto_es_fraude():
    assert rule(r=risk(score=POLICY["rules"]["fraud_score_high"])) == "R7"      # 40 → R7


def test_borde_score_igual_a_tau_bajo_es_zona_gris():
    assert rule(r=risk(score=POLICY["rules"]["fraud_score_low"])) == "R9"       # 30 → R9


def test_borde_score_justo_debajo_de_tau_bajo_es_normal():
    assert rule(r=risk(score=POLICY["rules"]["fraud_score_low"] - 0.01)) == "R12"  # 29.99 → R12


def test_borde_monto_igual_al_limite_no_escala():
    limite = POLICY["rules"]["amount_usd_max"]["Purchase"]
    assert rule(r=risk(amount_usd=limite)) == "R12"                            # "mayor que", no "mayor o igual"


def test_borde_ventana_exacta_no_escala():
    assert rule(t=tx(days_ago=POLICY["rules"]["claim_window_days"])) == "R12"


def test_tipo_desconocido_usa_limite_default():
    assert rule(t=tx(tx_type="Otro"), r=risk(amount_usd=POLICY["rules"]["amount_usd_max"]["default"] + 1)) == "R10"


# --- Precedencia: si aplican dos reglas, gana la de arriba ----------------------------

def test_precedencia_declined_gana_a_fraude():
    assert rule(t=tx(status="Declined"), r=risk(score=90)) == "R2"


def test_precedencia_fraude_gana_a_monto_alto():
    assert rule(r=risk(score=90, amount_usd=99999)) == "R7"


def test_cada_decision_lleva_version_y_motivo():
    d = evaluate(tx(), risk(score=35), {}, "cargo_no_reconocido", POLICY)
    assert d.policy_version == POLICY["policy_version"] and d.reason and d.queue == "fraude"
