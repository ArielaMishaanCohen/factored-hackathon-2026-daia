"""Campos de la traza para los graders de la evaluación (Ariela, 6.1 paso 9) y un arreglo de flujo.

1. tool.create_handoff → handoff_id, handoff_reason, suggested_queue, priority
2. TraceTurn → assistant_messages, ui_type, ui_transaction_ids, pending_action
3. TraceTurn → input_action (botón) y confirmation (texto "sí"/"no" del NLU)
4. verify.case_exists → case_id, dispute_type, priority, sla_due_at
5. Flujo: en IDENTIFICAR_TRANSACCION, un mensaje con datos (fecha, monto, comercio) no se
   abstiene por τ: la intención ya se conoce del turno anterior.
"""
from datetime import date

from app import orchestrator
from app.schemas import NLUResult
from app.store import store


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _ui(client, h, r, tipo="confirm"):
    return _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": tipo, "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})


def _turno(r, i=-1):
    return store.traces[r["trace_id"]].turns[i]


def _span(turno, nombre):
    return next(s for s in turno.spans if s.name == nombre)


# --- 1. Handoff -------------------------------------------------------------------------------

def test_span_del_handoff_trae_motivo_cola_y_prioridad(client, auth):
    h = auth("CUS-DEMO-02")
    r = _ui(client, h, _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"}))
    assert _span(_turno(r), "tool.create_handoff").output == {
        "handoff_id": r["handoff_id"], "handoff_reason": "POLICY_ESCALATION",
        "suggested_queue": "disputas", "priority": "high"}


# --- 2. Lo que vio el cliente -------------------------------------------------------------------

def test_turno_guarda_mensajes_ui_y_opciones(client, auth):
    r = _chat(client, auth("CUS-DEMO-02"), message="Me cobraron dos veces 120000")
    t = _turno(r)
    assert t.assistant_messages == [m["text"] for m in r["messages"]]
    assert t.ui_type == "transaction_options"
    assert t.ui_transaction_ids == [o["transaction_id"] for o in r["ui"]["options"]]
    assert t.pending_action is None


def test_turno_guarda_la_accion_pendiente(client, auth):
    r = _chat(client, auth("CUS-DEMO-01"), message="No reconozco un cargo de 350 en Oxxo")
    t = _turno(r)
    assert (t.ui_type, t.pending_action) == ("confirmation", "create_dispute_case")


# --- 3. Qué mandó el cliente --------------------------------------------------------------------

def test_input_action_distingue_confirmar_de_cancelar(client, auth):
    h = auth("CUS-DEMO-01")
    r = _ui(client, h, _chat(client, h, message="No reconozco un cargo de 350 en Oxxo"), "cancel")
    assert _turno(r).input_action == "cancel" and _turno(r, 0).input_action is None


def test_confirmacion_escrita_queda_en_la_traza(client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    r = _chat(client, h, conversation_id=r["conversation_id"], message="sí")
    t = _turno(r)
    assert (t.input_kind, t.input_action, t.confirmation) == ("message", None, "yes")
    assert t.actions[0].status == "verified"


# --- 4. Datos del caso ---------------------------------------------------------------------------

def test_verify_case_exists_trae_tipo_prioridad_y_sla(client, auth):
    h = auth("CUS-DEMO-01")
    r = _ui(client, h, _chat(client, h, message="No reconozco un cargo de 350 en Oxxo"))
    out = _span(_turno(r), "verify.case_exists").output
    assert out == {"verified": True, "case_id": "DSP-000001", "dispute_type": "cargo_no_reconocido",
                   "priority": "medium", "sla_due_at": r["case"]["sla_due_at"]}


# --- 5. Flujo: responder la pregunta del bot con datos no depende de τ ----------------------------

def test_dato_en_identificar_transaccion_no_se_abstiene(client, auth, monkeypatch):
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, message="Me cobraron dos veces 120000")
    assert r["state"] == "IDENTIFICAR_TRANSACCION"
    # El clasificador duda (bajo τ), pero el mensaje trae una fecha: es la respuesta a "¿cuál es?"
    monkeypatch.setattr(orchestrator, "understand_con_uso", lambda text, state=None: (NLUResult(
        language="es", intent="cargo_no_reconocido", intent_confidence=0.5, abstain=True,
        date_from=date(2026, 6, 9), date_to=date(2026, 6, 9), extractor="rules", model_version="t"), None))
    r = _chat(client, h, conversation_id=r["conversation_id"], message="es el pago del 9 de junio")
    assert r["state"] != "ACLARAR"
    assert store.conversations[r["conversation_id"]].data["transaction_id"] == "TX-DEMO-0005"
    assert _span(_turno(r), "nlu.understand").output["intent_from_context"] is True


def test_sin_datos_sigue_pidiendo_aclaracion(client, auth, monkeypatch):
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, message="Me cobraron dos veces 120000")
    monkeypatch.setattr(orchestrator, "understand_con_uso", lambda text, state=None: (NLUResult(
        language="es", intent="cargo_no_reconocido", intent_confidence=0.5, abstain=True,
        extractor="rules", model_version="t"), None))
    r = _chat(client, h, conversation_id=r["conversation_id"], message="mmm no sé")
    assert r["state"] == "ACLARAR"
