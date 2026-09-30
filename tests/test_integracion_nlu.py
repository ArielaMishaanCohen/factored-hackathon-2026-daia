"""Paso 10: el orquestador usa todo lo que entrega el NLU de ML (Fase 4) y la redacción.

1. understand recibe el estado de la conversación (para que "no" solo cancele al confirmar).
2. Moneda y fechas llegan a search_transactions (antes solo monto y comercio).
3. "la segunda" / "la última" eligen entre las opciones mostradas (op-04: -1 = la última).
4. Tokens y costo de Gemini (NLU y redacción) quedan en la traza.
5. Las respuestas pasan por compose() (Gemini + verificador) y, si algo falla, usan la plantilla.
"""
from datetime import date

from app import orchestrator
from app.llm.gemini_client import LLMUsage
from app.schemas import NLUResult
from app.store import store

USO = LLMUsage(model="gemini-test", tokens_in=100, tokens_out=20, cost_usd=0.0005)


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _nlu(**campos) -> NLUResult:
    base = dict(language="es", intent="cargo_no_reconocido", intent_confidence=0.99, abstain=False,
                extractor="llm", model_version="test+extraccion_v1")
    return NLUResult(**{**base, **campos})


# --- 1. El estado llega al NLU ------------------------------------------------------------

def test_understand_recibe_el_estado(client, auth, monkeypatch):
    vistos = []
    real = orchestrator.understand_con_uso
    monkeypatch.setattr(orchestrator, "understand_con_uso",
                        lambda text, state=None: vistos.append(state) or real(text, state))
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    _chat(client, h, conversation_id=r["conversation_id"], message="sí")
    assert vistos == ["INICIO", "CONFIRMAR_ACCION"]


def test_frase_larga_con_no_no_cancela_la_confirmacion(client, auth):
    """'No reconozco otro cargo…' mientras se espera una confirmación es un pedido nuevo, no un 'no'."""
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    pa = r["ui"]["pending_action"]["pending_action_id"]
    r = _chat(client, h, conversation_id=r["conversation_id"], message="No reconozco otro cargo de 89,90")
    assert "no hice ningún cambio" not in r["messages"][0]["text"]
    assert not store.pending_actions[pa].used


# --- 2. Moneda y fechas llegan a la búsqueda ---------------------------------------------

def test_moneda_y_fechas_llegan_a_la_busqueda(client, auth, monkeypatch):
    llamadas = []
    real = orchestrator.transactions.search_transactions
    monkeypatch.setattr(orchestrator.transactions, "search_transactions",
                        lambda session, **kw: llamadas.append(kw) or real(session, **kw))
    monkeypatch.setattr(orchestrator, "understand_con_uso", lambda text, state=None: (_nlu(
        amount=350.0, currency="USD", date_from=date(2026, 6, 1), date_to=date(2026, 6, 15),
        merchant_hint="Oxxo"), None))
    _chat(client, auth("CUS-DEMO-01"), message="No reconozco 350 USD en Oxxo a inicios de junio")
    assert llamadas == [{"amount": 350.0, "currency": "USD", "date_from": date(2026, 6, 1),
                         "date_to": date(2026, 6, 15), "merchant": "Oxxo"}]


# --- 3. Elegir una opción escribiendo ------------------------------------------------------

def _opciones(client, h):
    r = _chat(client, h, message="Me cobraron dos veces 120000")
    assert r["ui"]["type"] == "transaction_options" and len(r["ui"]["options"]) == 2
    return r


def test_la_segunda_elige_la_segunda_opcion(client, auth):
    h = auth("CUS-DEMO-02")
    r = _opciones(client, h)
    segunda = r["ui"]["options"][1]["transaction_id"]
    r = _chat(client, h, conversation_id=r["conversation_id"], message="la segunda")
    assert r["state"] == "CONFIRMAR_ACCION"
    assert store.conversations[r["conversation_id"]].data["transaction_id"] == segunda


def test_la_ultima_es_menos_uno(client, auth, monkeypatch):
    h = auth("CUS-DEMO-02")
    r = _opciones(client, h)
    ultima = r["ui"]["options"][-1]["transaction_id"]
    monkeypatch.setattr(orchestrator, "understand_con_uso",
                        lambda text, state=None: (_nlu(selected_option=-1, intent_confidence=0.3, abstain=True), None))
    r = _chat(client, h, conversation_id=r["conversation_id"], message="a última")
    assert store.conversations[r["conversation_id"]].data["transaction_id"] == ultima


def test_opcion_que_no_existe_vuelve_a_mostrar_las_opciones(client, auth, monkeypatch):
    h = auth("CUS-DEMO-02")
    r = _opciones(client, h)
    monkeypatch.setattr(orchestrator, "understand_con_uso",
                        lambda text, state=None: (_nlu(selected_option=5), None))
    r = _chat(client, h, conversation_id=r["conversation_id"], message="la quinta")
    assert r["ui"]["type"] == "transaction_options" and len(r["ui"]["options"]) == 2


# --- 4. Tokens y costo en la traza ---------------------------------------------------------

def test_uso_del_nlu_queda_en_la_traza(client, auth, monkeypatch):
    real = orchestrator.understand_con_uso
    monkeypatch.setattr(orchestrator, "understand_con_uso",
                        lambda text, state=None: (real(text, state)[0], USO))
    r = _chat(client, auth("CUS-DEMO-01"), message="No reconozco un cargo de 350 en Oxxo")
    turno = store.traces[r["trace_id"]].turns[0]
    span = next(s for s in turno.spans if s.name == "nlu.understand")
    assert (span.model, span.tokens_in, span.tokens_out, span.cost_usd) == ("gemini-test", 100, 20, 0.0005)
    assert turno.tokens_in == 100 and turno.cost_usd == 0.0005


# --- 5. Redacción con compose() ------------------------------------------------------------

def test_respuestas_pasan_por_compose(client, auth, monkeypatch):
    monkeypatch.setattr(orchestrator, "compose", lambda key, lang, facts: (f"[llm] {key}", "llm", USO))
    r = _chat(client, auth("CUS-DEMO-01"), message="No reconozco un cargo de 350 en Oxxo")
    assert r["messages"][0] == {"role": "assistant", "text": "[llm] confirm_case", "source": "llm"}
    assert r["audit"]["fallback_used"] is False
    turno = store.traces[r["trace_id"]].turns[0]
    assert any(s.name == "llm.compose" and s.tokens_in == 100 for s in turno.spans)


def test_si_compose_falla_se_usa_la_plantilla(client, auth, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("Gemini explotó")
    monkeypatch.setattr(orchestrator, "compose", roto)
    r = _chat(client, auth("CUS-DEMO-01"), message="No reconozco un cargo de 350 en Oxxo")
    assert r["messages"][0]["source"] == "template" and "350.00 USD" in r["messages"][0]["text"]
    assert r["audit"]["fallback_used"] is True


def test_sin_gemini_todo_sale_de_plantillas(client, auth):
    """En los tests no hay GEMINI_API_KEY: compose devuelve la plantilla y el flujo sigue igual."""
    r = _chat(client, auth("CUS-DEMO-01"), message="No reconozco un cargo de 350 en Oxxo")
    assert r["messages"][0]["source"] == "template" and r["audit"]["fallback_used"] is True


# --- Otros -----------------------------------------------------------------------------------

def test_health_muestra_el_modelo_real(client):
    from app.nlu.classifier import get_classifier
    clf = get_classifier()
    esperado = clf.model_version if clf else "stub-keywords-0"
    assert client.get("/api/health").json()["intent_model"] == esperado


def test_aclaracion_explica_que_si_puede_hacer(client, auth):
    """Aunque el modelo se abstenga, la respuesta dice para qué sirve el bot (escenario 'no soportado')."""
    r = _chat(client, auth("CUS-DEMO-01"), message="hola")
    assert r["state"] == "ACLARAR"
    assert "cargos que no reconoces" in r["messages"][0]["text"]
