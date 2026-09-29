"""Persistencia (Fase 3, paso 6): si el servidor se reinicia, no se pierde nada.

"Reiniciar" se simula así: se borra todo de la memoria y se vuelve a cargar desde
el archivo SQLite, exactamente lo que pasa cuando uvicorn o Render arrancan de nuevo.
"""
import sqlite3

import pytest

from app import store as store_module
from app.store import simulate_restart, store


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Un SQLite en un archivo temporal (los demás tests usan uno en memoria)."""
    path = tmp_path / "ops.sqlite"
    store_module.use_database(path)
    yield path
    store_module.use_database(":memory:")


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_el_caso_sobrevive_a_un_reinicio(db, client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})

    simulate_restart()

    assert [c["case_id"] for c in client.get("/api/cases", headers=h).json()["cases"]] == ["DSP-000001"]


def test_la_conversacion_sigue_despues_del_reinicio(db, client, auth):
    """El cliente pidió registrar la disputa, el servidor se reinició, y el 'Confirmar' igual funciona."""
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")

    simulate_restart()

    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    assert r["case"]["case_id"] == "DSP-000001"


def test_los_numeros_de_caso_no_se_repiten_tras_reinicio(db, client, auth):
    for cid, msg in [("CUS-DEMO-01", "No reconozco un cargo de 350 en Oxxo")]:
        h = auth(cid)
        r = _chat(client, h, message=msg)
        _chat(client, h, conversation_id=r["conversation_id"], ui_action={
            "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    simulate_restart()
    assert store.next_id("DSP") == "DSP-000002"


def test_sesion_expirada_sigue_expirada_tras_reinicio(db, client, auth):
    h = auth("CUS-DEMO-01")
    client.post("/api/auth/demo/expire", headers=h)
    simulate_restart()
    assert client.post("/api/chat", headers=h, json={"message": "hola"}).status_code == 401


def test_el_handoff_y_la_traza_sobreviven(db, client, auth):
    h = auth("CUS-DEMO-02")
    r = _chat(client, h, ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})
    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    simulate_restart()
    assert len(store.handoffs) == 1 and r["trace_id"] in store.traces


def test_las_tablas_existen_en_sqlite(db, client, auth):
    auth("CUS-DEMO-01")
    client.post("/api/chat", headers=auth("CUS-DEMO-01"), json={"message": "hola"})
    tablas = {r[0] for r in sqlite3.connect(db).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"conversations", "pending_actions", "cases", "card_blocks", "handoffs", "traces",
            "revoked_sessions", "used_confirmation_tokens", "sequences"} <= tablas


def test_reset_store_deja_la_base_vacia(db, client, auth):
    """Los tests (y la evaluación) necesitan poder empezar de cero entre casos."""
    h = auth("CUS-DEMO-01")
    _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    store_module.reset_store()
    simulate_restart()
    assert not store.conversations and not store.pending_actions
