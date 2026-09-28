"""Contrato de la API (design.md, secciones 6 y 7) sobre los stubs de Fase 1.

Estos tests deben seguir pasando cuando C reemplace los stubs por la implementación real.
"""
from app.schemas import ChatResponse, HandoffPackage


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["policy_version"]


def test_login_rejects_wrong_otp(client):
    r = client.post("/api/auth/login", json={"customer_id": "CUS-DEMO-01", "otp": "000000"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_chat_requires_token(client):
    r = client.post("/api/chat", json={"message": "hola"})
    assert r.status_code == 401


def test_happy_path_creates_verified_case(client, auth):
    h = auth()
    r = client.post("/api/chat", headers=h, json={"message": "No reconozco un cargo de 350 en Oxxo"})
    body = ChatResponse.model_validate(r.json())
    assert body.ui.type == "confirmation" and body.audit.rule_id == "R12"

    pa = body.ui.pending_action.pending_action_id
    r = client.post("/api/chat", headers=h, json={"conversation_id": body.conversation_id,
                                                  "ui_action": {"type": "confirm", "pending_action_id": pa}})
    body = ChatResponse.model_validate(r.json())
    assert body.ui.type == "case_created" and body.case.case_id.startswith("DSP-")

    # Doble confirmación no duplica el caso
    r = client.post("/api/chat", headers=h, json={"conversation_id": body.conversation_id,
                                                  "ui_action": {"type": "confirm", "pending_action_id": pa}})
    assert r.json()["case"] is None
    assert len(client.get("/api/cases", headers=h).json()["cases"]) == 1


def test_multiple_candidates_show_options(client, auth):
    h = auth("CUS-DEMO-02")
    body = client.post("/api/chat", headers=h, json={"message": "Me cobraron dos veces 120000"}).json()
    assert body["ui"]["type"] == "transaction_options" and len(body["ui"]["options"]) == 2


def test_out_of_scope_abstains(client, auth):
    body = client.post("/api/chat", headers=auth(), json={"message": "Quiero un préstamo"}).json()
    assert body["state"] == "ABSTENERSE" and body["ui"] is None


def test_other_customers_transaction_is_not_found(client, auth):
    h = auth("CUS-DEMO-01")
    conv = client.post("/api/chat", headers=h, json={"message": "Quiero un préstamo"}).json()["conversation_id"]
    body = client.post("/api/chat", headers=h, json={
        "conversation_id": conv, "ui_action": {"type": "select_transaction", "transaction_id": "TX-DEMO-0006"}}).json()
    assert body["audit"]["rule_id"] == "R1" and "3500" not in str(body)


def test_conversation_of_other_customer_is_not_found(client, auth):
    conv = client.post("/api/chat", headers=auth("CUS-DEMO-01"), json={"message": "hola"}).json()["conversation_id"]
    r = client.post("/api/chat", headers=auth("CUS-DEMO-02"), json={"conversation_id": conv, "message": "hola"})
    assert r.status_code == 404


def test_expired_session(client, auth):
    h = auth()
    assert client.post("/api/auth/demo/expire", headers=h).status_code == 204
    r = client.post("/api/chat", headers=h, json={"message": "hola"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "SESSION_EXPIRED"


def test_fraud_blocks_card_and_hands_off(client, auth):
    h = auth("CUS-DEMO-03")
    body = client.post("/api/chat", headers=h, json={"message": "Não reconheço uma compra de 3.500"}).json()
    assert body["language"] == "pt" and body["audit"]["rule_id"] == "R7"
    assert body["ui"]["pending_action"]["action"] == "block_card"
    conv = body["conversation_id"]

    body = client.post("/api/chat", headers=h, json={"conversation_id": conv, "ui_action": {
        "type": "confirm", "pending_action_id": body["ui"]["pending_action"]["pending_action_id"]}}).json()
    assert body["ui"]["pending_action"]["action"] == "create_dispute_case"

    body = client.post("/api/chat", headers=h, json={"conversation_id": conv, "ui_action": {
        "type": "confirm", "pending_action_id": body["ui"]["pending_action"]["pending_action_id"]}}).json()
    assert body["ui"]["type"] == "handoff"

    # El cliente no ve la cola ni los datos de riesgo
    assert client.get("/api/handoffs", headers=h).status_code == 403
    trace = client.get(f"/api/traces/{body['trace_id']}", headers=h).json()
    assert "fraud_score" not in str(trace) and "transaction_risk" not in str(trace)

    agent = client.post("/api/auth/agent-login", json={"agent_id": "AGT-DEMO", "otp": "123456"}).json()
    ha = {"Authorization": f"Bearer {agent['access_token']}"}
    queue = client.get("/api/handoffs", headers=ha).json()["handoffs"]
    assert len(queue) == 1
    pkg = HandoffPackage.model_validate(client.get(f"/api/handoffs/{queue[0]['handoff_id']}", headers=ha).json())
    assert pkg.policy_decision.rule_id == "R7" and pkg.suggested_queue == "fraude"
    assert [a.action for a in pkg.actions_taken] == ["block_card", "create_dispute_case"]
    assert all(a.status == "verified" for a in pkg.actions_taken)
