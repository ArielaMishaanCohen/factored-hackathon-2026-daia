"""Pedidos de la evaluación (Ariela y Diego, 1-oct):

1. NLU_MODE=keywords → baseline B1: intención del stub, campos de las reglas, mensajes y resumen
   del handoff siempre de plantilla, sin Gemini aunque haya llave. Visible en /health y en la traza.
2. Comercios con tilde: "optica" encuentra "Óptica Visión" (y al revés).
3. El idioma de la conversación no cambia con mensajes sin señal clara ("88,88, Ferretería").
4. Con baja confianza pero con datos (monto, fecha o comercio) y una intención de disputa, se busca
   la transacción en vez de pedir "el monto, la fecha o el comercio" que ya vinieron.
"""
from datetime import date

import pytest

from app import orchestrator
from app.config import get_settings
from app.llm.gemini_client import LLMUsage
from app.nlu import understand_con_uso
from app.schemas import NLUResult
from app.store import store
from app.tools import stub_data


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _turno(r):
    return store.traces[r["trace_id"]].turns[-1]


@pytest.fixture
def keywords(monkeypatch):
    """NLU_MODE=keywords con una llave de Gemini fijada: igual no se tiene que llamar a Gemini."""
    monkeypatch.setenv("NLU_MODE", "keywords")
    monkeypatch.setenv("GEMINI_API_KEY", "llave-falsa-que-no-se-debe-usar")
    get_settings.cache_clear()
    from app.llm import gemini_client
    def prohibido(*a, **k):
        raise AssertionError("Con NLU_MODE=keywords no se llama a Gemini")
    monkeypatch.setattr(gemini_client, "get_client", prohibido)
    yield
    monkeypatch.delenv("NLU_MODE"); monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()


# --- 1. NLU_MODE=keywords ---------------------------------------------------------------------

def test_health_muestra_nlu_mode(client):
    assert client.get("/api/health").json()["nlu_mode"] == "full"


def test_keywords_health_y_nlu(client, keywords):
    body = client.get("/api/health").json()
    assert body["nlu_mode"] == "keywords" and body["intent_model"] == "stub-keywords-0"
    r, uso = understand_con_uso("No reconozco un cargo de 350 en Oxxo")
    assert r.model_version == "stub-keywords-0+rules" and r.extractor == "rules" and uso is None


def test_keywords_turnos_sin_gemini_y_costo_cero(client, auth, keywords):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    trace = store.traces[r["trace_id"]]
    assert all(t.versions["nlu_mode"] == "keywords" for t in trace.turns)
    assert trace.turns[0].versions["intent_model"] == "stub-keywords-0+rules"
    assert all(m["source"] == "template" for m in r["messages"]) and r["audit"]["fallback_used"]
    assert sum(t.cost_usd for t in trace.turns) == 0


def test_keywords_handoff_con_resumen_de_plantilla(client, auth, keywords):
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})
    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    assert r["state"] == "HANDOFF"
    assert next(iter(store.handoffs.values())).summary.startswith("Disputa sobre TX-DEMO-0005")


def test_nlu_mode_invalido_cae_a_full(monkeypatch):
    monkeypatch.setenv("NLU_MODE", "cualquiera"); get_settings.cache_clear()
    try:
        assert get_settings().nlu_mode == "full"
    finally:
        monkeypatch.delenv("NLU_MODE"); get_settings.cache_clear()


# --- 2. Comercios con tilde ---------------------------------------------------------------------

@pytest.mark.parametrize("escrito", ["optica", "Óptica", "OPTICA vision", "óptica visión"])
def test_comercio_sin_importar_tildes(client, auth, monkeypatch, escrito):
    monkeypatch.setattr(stub_data, "TRANSACTIONS", stub_data.TRANSACTIONS + [{
        "transaction_id": "TX-DEMO-0099", "customer_id": "CUS-DEMO-01", "product_id": "PRD-DEMO-01",
        "business_date": date(2026, 6, 12), "amount": 75.0, "currency": "USD", "amount_usd": 75.0,
        "merchant_name": "Óptica Visión", "transaction_type": "Purchase", "channel": "POS",
        "status": "Approved", "fraud_score": 3.0}])
    from app.tools import transactions
    from app.schemas import Session
    from datetime import datetime, timezone
    s = Session(session_id="s", customer_id="CUS-DEMO-01", role="customer", language="es",
                expires_at=datetime.now(timezone.utc))
    assert [t.transaction_id for t in transactions.search_transactions(s, merchant=escrito)] == ["TX-DEMO-0099"]


# --- 3. El idioma de la conversación se mantiene sin señal clara ------------------------------

def test_mensaje_sin_senal_no_cambia_el_idioma():
    r, _ = understand_con_uso("88,88, Ferretería", language="pt")
    assert r.language == "pt"
    r, _ = understand_con_uso("Não reconheço uma cobrança de 88,88", language="es")
    assert r.language == "pt"                         # con señal clara, sí cambia


def test_conversacion_en_portugues_sigue_en_portugues(client, auth):
    h = auth("CUS-DEMO-03")                           # sugerido: pt
    r = _chat(client, h, message="Não reconheço uma compra de 3.500")
    assert r["language"] == "pt"
    r = _chat(client, h, conversation_id=r["conversation_id"], message="3.500, Tienda online")
    assert r["language"] == "pt"


# --- 4. Baja confianza con datos → buscar --------------------------------------------------------

def _nlu_dudoso(**campos):
    base = dict(language="es", intent="cargo_no_reconocido", intent_confidence=0.5, abstain=True,
                extractor="rules", model_version="t")
    return lambda text, state=None, language=None: (NLUResult(**{**base, **campos}), None)


def test_baja_confianza_con_datos_busca(client, auth, monkeypatch):
    monkeypatch.setattr(orchestrator, "understand_con_uso", _nlu_dudoso(amount=350.0, merchant_hint="Oxxo"))
    r = _chat(client, auth("CUS-DEMO-01"), message="ayer 350 en oxxo, no fui yo")
    assert r["state"] == "CONFIRMAR_ACCION" and r["audit"]["rule_id"] == "R12"
    assert next(s for s in _turno(r).spans if s.name == "nlu.understand").output["intent_from_data"] is True


def test_baja_confianza_sin_datos_sigue_aclarando(client, auth, monkeypatch):
    monkeypatch.setattr(orchestrator, "understand_con_uso", _nlu_dudoso())
    assert _chat(client, auth("CUS-DEMO-01"), message="tengo un problema")["state"] == "ACLARAR"


@pytest.mark.parametrize("intent", ["fuera_de_alcance", "estado_disputa", "tarjeta_comprometida"])
def test_baja_confianza_no_disputa_no_busca(client, auth, monkeypatch, intent):
    """Préstamo con monto, o tarjeta robada dudosa (propondría un bloqueo): se aclara."""
    monkeypatch.setattr(orchestrator, "understand_con_uso", _nlu_dudoso(intent=intent, amount=5000.0))
    assert _chat(client, auth("CUS-DEMO-01"), message="quiero 5000")["state"] == "ACLARAR"
