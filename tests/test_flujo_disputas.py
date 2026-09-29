"""Tests del flujo de disputas (Fase 3, rol C).

Usan los helpers de tests/conftest.py:
  - client: un "navegador falso" que le habla a la API (y limpia el store).
  - auth("CUS-DEMO-01"): hace login y devuelve los headers con el token.
"""


def _chat(client, headers, **body):
    r = client.post("/api/chat", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _confirmar(client, headers, respuesta):
    pa = respuesta["ui"]["pending_action"]["pending_action_id"]
    return _chat(client, headers, conversation_id=respuesta["conversation_id"],
                 ui_action={"type": "confirm", "pending_action_id": pa})


def test_R5_no_duplica_disputa(client, auth):
    """Si ya hay un caso abierto por esa transacción, informa y NO ofrece crear otro."""
    h = auth("CUS-DEMO-01")
    _confirmar(client, h, _chat(client, h, message="No reconozco un cargo de 350 en Oxxo"))

    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    assert r["audit"]["rule_id"] == "R5"
    assert r["ui"] is None                           # nada que confirmar
    assert "DSP-000001" in r["messages"][0]["text"]  # dice cuál es el caso existente
    assert len(client.get("/api/cases", headers=h).json()["cases"]) == 1


def test_R5_en_portugues(client, auth):
    h = auth("CUS-DEMO-01")
    _confirmar(client, h, _chat(client, h, message="No reconozco un cargo de 350 en Oxxo"))
    r = _chat(client, h, message="Não reconheço uma cobrança de 350")
    assert r["language"] == "pt" and r["audit"]["rule_id"] == "R5"
    assert "contestação aberta" in r["messages"][0]["text"]


def test_R8_score_nulo_escala_con_caso_y_handoff(client, auth):
    """De punta a punta: TX-DEMO-0005 no tiene fraud_score → se crea el caso y va a un humano."""
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})
    assert r["audit"]["rule_id"] == "R8"
    assert r["ui"]["pending_action"]["action"] == "create_dispute_case"   # igual pide confirmación

    r = _confirmar(client, h, r)
    assert r["state"] == "HANDOFF" and r["ui"]["type"] == "handoff"
    assert r["case"]["status"] == "Escalated" and r["case"]["priority"] == "high"
    assert "fraud_score" not in str(r)                                     # el cliente no ve el riesgo
