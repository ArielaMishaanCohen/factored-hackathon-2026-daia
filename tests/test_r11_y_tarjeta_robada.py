"""Dudas de la evaluación (Ariela, Fase 6.1):

1. R11 cuenta las disputas de los últimos 90 días SIN importar el estado (design.md §3.2):
   las cerradas cuentan, y las viejas (más de 90 días) no.
2. Tarjeta comprometida: en cuanto se identifica la transacción, se propone bloquear SU
   tarjeta, sea cual sea la regla (incluso R2 rechazada). Luego se sigue con la política
   y, si no hay nada que disputar, igual se pasa a la cola de fraude.
"""
from datetime import datetime, timedelta, timezone

from app import orchestrator
from app.schemas import DisputeCase, NLUResult
from app.store import store


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _ui(client, h, r, tipo="confirm"):
    return _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": tipo, "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})


def _caso(n, customer, status, dias_atras):
    creado = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    store.cases[f"DSP-9{n:05d}"] = DisputeCase(
        case_id=f"DSP-9{n:05d}", customer_id=customer, transaction_id=f"TX-VIEJA-{n}", product_id="PRD-X",
        dispute_type="cargo_no_reconocido", category="Transactions", subcategory="Cargo no reconocido",
        priority="medium", status=status, rule_id="R12", policy_version="test", language="es",
        created_at=creado, sla_due_at=creado + timedelta(days=10))


# --- 1. R11 ---------------------------------------------------------------------------------

def test_R11_cuentan_las_disputas_cerradas_recientes(client, auth):
    for n in range(3):
        _caso(n, "CUS-DEMO-02", "Closed", dias_atras=10)
    r = _chat(client, auth("CUS-DEMO-02"), ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0003"})
    assert r["audit"]["rule_id"] == "R11"


def test_R11_no_cuentan_las_de_hace_mas_de_90_dias(client, auth):
    for n in range(3):
        _caso(n, "CUS-DEMO-02", "Open", dias_atras=120)
    r = _chat(client, auth("CUS-DEMO-02"), ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0003"})
    assert r["audit"]["rule_id"] == "R12"


def test_R11_no_cuentan_las_de_otro_cliente(client, auth):
    for n in range(3):
        _caso(n, "CUS-DEMO-01", "Open", dias_atras=5)
    r = _chat(client, auth("CUS-DEMO-02"), ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0003"})
    assert r["audit"]["rule_id"] == "R12"


# --- 2. Tarjeta comprometida ----------------------------------------------------------------

def _robada(monkeypatch, **campos):
    """El NLU entiende 'me robaron la tarjeta' (no dependemos del clasificador en estos tests)."""
    def fake(text, state=None):
        base = dict(language="es", intent="tarjeta_comprometida", intent_confidence=0.99, abstain=False,
                    extractor="rules", model_version="test")
        return NLUResult(**{**base, **campos}), None
    monkeypatch.setattr(orchestrator, "understand_con_uso", fake)


def test_robada_con_cargo_rechazado_igual_propone_bloquear(client, auth, monkeypatch):
    """TX-DEMO-0002 está Declined (R2). Antes: solo informaba y no bloqueaba nada."""
    _robada(monkeypatch, amount=89.9)
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="me robaron la tarjeta, hay un cargo de 89,90")
    assert r["audit"]["rule_id"] == "R2"
    assert r["ui"]["pending_action"]["action"] == "block_card"

    r = _ui(client, h, r)
    textos = " ".join(m["text"] for m in r["messages"])
    assert "bloqueada" in textos and "rechazado" in textos       # bloqueó y explicó que no hubo cobro
    assert r["state"] == "HANDOFF" and r["case"] is None           # nada que disputar, pero va a fraude
    pkg = next(iter(store.handoffs.values()))
    assert pkg.suggested_queue == "fraude" and pkg.actions_taken[0].action == "block_card"
    assert store.card_blocks["PRD-DEMO-01"].status == "Blocked"


def test_robada_y_cancela_el_bloqueo_igual_va_a_fraude(client, auth, monkeypatch):
    _robada(monkeypatch, amount=89.9)
    h = auth("CUS-DEMO-01")
    r = _ui(client, h, _chat(client, h, message="me robaron la tarjeta, cargo de 89,90"), "cancel")
    assert r["state"] == "HANDOFF"
    pkg = next(iter(store.handoffs.values()))
    assert pkg.actions_declined == ["block_card"] and pkg.suggested_queue == "fraude"
    assert "PRD-DEMO-01" not in store.card_blocks


def test_robada_con_cargo_valido_sigue_igual_que_antes(client, auth, monkeypatch):
    """R7 por intención: bloqueo → caso Crítico → handoff (no cambia)."""
    _robada(monkeypatch, amount=350.0)
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="me robaron la tarjeta y hay un cargo de 350")
    assert r["audit"]["rule_id"] == "R7" and r["ui"]["pending_action"]["action"] == "block_card"
    r = _ui(client, h, r)
    assert r["ui"]["pending_action"]["action"] == "create_dispute_case"
    r = _ui(client, h, r)
    assert r["state"] == "HANDOFF" and r["case"]["priority"] == "critical"


def test_tarjeta_ya_bloqueada_no_se_vuelve_a_proponer(client, auth, monkeypatch):
    from app.schemas import CardStatus
    store.card_blocks["PRD-DEMO-01"] = CardStatus(product_id="PRD-DEMO-01", card_mask="•••• 4821",
                                                  status="Blocked", blocked_at=datetime.now(timezone.utc))
    _robada(monkeypatch, amount=89.9)
    r = _chat(client, auth("CUS-DEMO-01"), message="me robaron la tarjeta, cargo de 89,90")
    assert r["ui"] is None or r["ui"]["type"] != "confirmation"
