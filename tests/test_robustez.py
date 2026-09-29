"""Tests de robustez (Fase 3, paso 3): qué pasa cuando las cosas salen MAL.

1. Una herramienta falla (timeout): el sistema reintenta y, si sigue fallando,
   NO revienta con error 500 ni dice "listo": pasa el caso a un humano.
2. El cliente cancela en un caso que requiere humano: igual se hace handoff.
3. El cliente no se deja entender: máximo 2 aclaraciones y luego handoff.
"""
import pytest

from app.config import get_settings
from app.store import store


def _chat(client, headers, **body):
    r = client.post("/api/chat", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _ui(client, headers, respuesta, tipo):
    pa = respuesta["ui"]["pending_action"]["pending_action_id"]
    return _chat(client, headers, conversation_id=respuesta["conversation_id"],
                 ui_action={"type": tipo, "pending_action_id": pa})


@pytest.fixture
def fallas(monkeypatch):
    """Activa FAULT_INJECTION=true solo durante el test."""
    monkeypatch.setenv("FAULT_INJECTION", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("FAULT_INJECTION")
    get_settings.cache_clear()


# --- 1. Fallas de herramientas ---------------------------------------------------------

def test_timeout_al_crear_caso_hace_handoff_y_no_miente(client, auth, fallas):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    h_falla = {**h, "X-Fault-Inject": "create_dispute_case"}
    r = _ui(client, h_falla, r, "confirm")

    assert r["state"] == "HANDOFF" and r["ui"]["type"] == "handoff"
    assert r["case"] is None                                   # no se creó nada…
    assert "Registré" not in r["messages"][0]["text"]          # …y no dice que sí
    pkg = next(iter(store.handoffs.values()))
    assert pkg.handoff_reason == "TOOL_FAILURE"
    assert pkg.actions_taken[0].status == "failed"
    assert pkg.open_questions                                  # le dice al humano qué revisar


def test_reintentos_quedan_en_la_traza(client, auth, fallas):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    r = _ui(client, {**h, "X-Fault-Inject": "create_dispute_case"}, r, "confirm")
    trace = store.traces[r["trace_id"]]
    span = next(s for s in trace.turns[-1].spans if s.name == "tool.create_dispute_case")
    assert span.output["attempts"] == 3                        # 1 intento + 2 reintentos
    assert "TIMEOUT" in span.error


def test_timeout_al_buscar_no_da_error_500(client, auth, fallas):
    h = {**auth("CUS-DEMO-01"), "X-Fault-Inject": "search_transactions"}
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    assert r["state"] == "HANDOFF"


def test_sin_fault_injection_el_header_se_ignora(client, auth):
    """En producción (FAULT_INJECTION=false) nadie puede forzar fallas con un header."""
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    r = _ui(client, {**h, "X-Fault-Inject": "create_dispute_case"}, r, "confirm")
    assert r["state"] == "CERRAR" and r["case"]["case_id"] == "DSP-000001"


# --- 2. Cancelar en un caso que requiere humano ---------------------------------------

def test_cancelar_bloqueo_por_fraude_igual_hace_handoff(client, auth):
    h = auth("CUS-DEMO-03")
    r = _chat(client, h, message="Não reconheço uma compra de 3.500")
    assert r["ui"]["pending_action"]["action"] == "block_card"
    r = _ui(client, h, r, "cancel")

    assert r["state"] == "HANDOFF"
    pkg = next(iter(store.handoffs.values()))
    assert pkg.actions_declined == ["block_card"]              # el humano sabe que dijo que no
    assert pkg.policy_decision.rule_id == "R7" and pkg.suggested_queue == "fraude"


def test_cancelar_caso_normal_solo_cierra(client, auth):
    h = auth("CUS-DEMO-01")
    r = _ui(client, h, _chat(client, h, message="No reconozco un cargo de 350 en Oxxo"), "cancel")
    assert r["state"] == "CERRAR" and not store.handoffs


# --- 3. Límite de aclaraciones y de búsquedas sin resultado ---------------------------

def test_dos_aclaraciones_y_luego_handoff(client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="hola")
    conv = r["conversation_id"]
    assert r["state"] == "ACLARAR"
    assert _chat(client, h, conversation_id=conv, message="mmm")["state"] == "ACLARAR"
    r = _chat(client, h, conversation_id=conv, message="no sé")
    assert r["state"] == "HANDOFF"
    assert next(iter(store.handoffs.values())).handoff_reason == "CLARIFICATION_EXHAUSTED"


def test_dos_busquedas_vacias_y_luego_handoff(client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 777")
    conv = r["conversation_id"]
    assert "No encontré" in r["messages"][0]["text"]
    _chat(client, h, conversation_id=conv, message="No reconozco un cargo de 778")
    r = _chat(client, h, conversation_id=conv, message="No reconozco un cargo de 779")
    assert r["state"] == "HANDOFF"
    assert next(iter(store.handoffs.values())).handoff_reason == "NO_TRANSACTION_FOUND"
