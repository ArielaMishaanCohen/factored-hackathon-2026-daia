"""Trazas y métricas de operación (Fase 7).

La traza es la "caja negra": qué pasó en cada turno. La evaluación (A + B) califica
los casos leyendo estos campos, así que su forma no cambia sin avisar.
"""
import json
import logging

from app.config import get_policy
from app.store import store


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _agente(client):
    tok = client.post("/api/auth/agent-login", json={"agent_id": "AGT-DEMO", "otp": "123456"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _caso_completo(client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    return h, r


def test_cada_turno_guarda_lo_que_necesita_la_evaluacion(client, auth):
    _, r = _caso_completo(client, auth)
    t1, t2 = store.traces[r["trace_id"]].turns

    assert t1.input_kind == "message" and t2.input_kind == "ui_action"
    assert t1.intent == "cargo_no_reconocido" and t1.intent_confidence > 0
    assert t1.rule_id == "R12" and t1.state_to == "CONFIRMAR_ACCION"
    assert t1.latency_ms is not None and t1.started_at is not None
    assert [(a.action, a.status) for a in t2.actions] == [("create_dispute_case", "verified")]
    assert t2.case_id == "DSP-000001"


def test_la_traza_lleva_versiones(client, auth):
    _, r = _caso_completo(client, auth)
    v = store.traces[r["trace_id"]].turns[0].versions
    assert v["policy_version"] == get_policy()["policy_version"]   # la versión configurada, no un número fijo
    assert v["intent_model"] and v["data_source"] == "stub"         # los tests corren con los stubs (conftest.py)
    assert "llm_model" in v


def test_tokens_y_costo_suman_los_spans(client, auth):
    _, r = _caso_completo(client, auth)
    t = store.traces[r["trace_id"]].turns[0]
    assert t.tokens_in == 0 and t.tokens_out == 0 and t.cost_usd == 0.0   # sin LLM todavía: costo cero real


def test_el_cliente_ve_su_traza_sin_datos_de_riesgo(client, auth):
    h, r = _caso_completo(client, auth)
    trace = client.get(f"/api/traces/{r['trace_id']}", headers=h).json()
    assert trace["turns"][0]["rule_id"] == "R12"
    assert "get_transaction_risk" not in json.dumps(trace)


def test_log_por_turno_sin_texto_del_cliente(client, auth, caplog):
    with caplog.at_level(logging.INFO, logger="latam.trace"):
        _caso_completo(client, auth)
    lineas = [json.loads(r.getMessage()) for r in caplog.records if r.name == "latam.trace"]
    assert len(lineas) == 2 and lineas[0]["rule_id"] == "R12" and "latency_ms" in lineas[0]
    assert "Oxxo" not in caplog.text               # no se loguea lo que escribió el cliente


def test_metricas_para_el_agente(client, auth):
    _caso_completo(client, auth)
    h = auth("CUS-DEMO-02")
    _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})

    m = client.get("/api/ops/metrics", headers=_agente(client)).json()
    assert m["conversations"] == 2 and m["turns"] == 3
    assert m["rules"]["R12"] == 1 and m["rules"]["R8"] == 1
    assert m["cases_created"] == 1
    assert m["latency_ms"]["p50"] is not None and m["latency_ms"]["p95"] is not None
    assert m["tool_errors"] == {}


def test_metricas_cuentan_handoffs_y_errores_de_herramientas(client, auth, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("FAULT_INJECTION", "true"); get_settings.cache_clear()
    try:
        h = auth("CUS-DEMO-01")
        r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
        client.post("/api/chat", headers={**h, "X-Fault-Inject": "create_dispute_case"}, json={
            "conversation_id": r["conversation_id"],
            "ui_action": {"type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]}})
    finally:
        monkeypatch.delenv("FAULT_INJECTION"); get_settings.cache_clear()
    m = client.get("/api/ops/metrics", headers=_agente(client)).json()
    assert m["handoffs_by_reason"] == {"TOOL_FAILURE": 1}
    assert m["tool_errors"] == {"create_dispute_case": 1}
    assert m["actions"]["failed"] == 1


def test_cliente_no_puede_ver_metricas(client, auth):
    assert client.get("/api/ops/metrics", headers=auth("CUS-DEMO-01")).status_code == 403


def test_la_traza_dice_que_transaccion_y_con_que_prioridad_y_cola(client, auth):
    """Para los graders de la evaluación: sin leer el estado interno de la conversación."""
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})
    turno = store.traces[r["trace_id"]].turns[-1]
    assert turno.transaction_id == "TX-DEMO-0005" and turno.rule_id == "R8"
    span = next(s for s in turno.spans if s.name == "policy.evaluate")
    assert span.output == {"rule_id": "R8", "action": "ESCALATE", "priority": "high",
                           "queue": "disputas", "transaction_id": "TX-DEMO-0005"}


def test_sin_transaccion_todavia_el_campo_va_vacio(client, auth):
    r = _chat(client, auth("CUS-DEMO-01"), message="hola")
    assert store.traces[r["trace_id"]].turns[-1].transaction_id is None
