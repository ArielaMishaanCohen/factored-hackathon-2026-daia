"""El backend funciona igual leyendo gold.duckdb que leyendo los stubs.

Crea un gold.duckdb de prueba (scripts/make_demo_gold.py) en una carpeta temporal,
apunta GOLD_DB_PATH a él y recorre los flujos clave.
"""
import importlib.util
from pathlib import Path

import pytest

from app.config import get_settings
from app.store import store
from app.tools import data_source

_spec = importlib.util.spec_from_file_location(
    "make_demo_gold", Path(__file__).resolve().parents[1] / "scripts" / "make_demo_gold.py")
make_demo_gold = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_demo_gold)


@pytest.fixture(autouse=True)
def gold(tmp_path, monkeypatch):
    path = make_demo_gold.build(tmp_path / "gold.duckdb")
    monkeypatch.setenv("GOLD_DB_PATH", str(path))
    get_settings.cache_clear()
    data_source.reset_connection()
    yield path
    data_source.reset_connection()
    monkeypatch.delenv("GOLD_DB_PATH")
    get_settings.cache_clear()


def _chat(client, h, **body):
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_dice_que_usa_gold(client):
    assert client.get("/api/health").json()["data_manifest"] == "gold:gold.duckdb"


def test_clientes_demo_salen_de_gold(client):
    ids = [c["customer_id"] for c in client.get("/api/auth/demo-customers").json()["customers"]]
    assert ids == ["CUS-DEMO-01", "CUS-DEMO-02", "CUS-DEMO-03"]


def test_camino_feliz_con_gold(client, auth):
    h = auth("CUS-DEMO-01")
    r = _chat(client, h, message="No reconozco un cargo de 350 en Oxxo")
    assert r["audit"]["rule_id"] == "R12"
    r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
        "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    assert r["case"]["case_id"] == "DSP-000001"


def test_con_gold_tampoco_se_ven_transacciones_ajenas(client, auth):
    r = _chat(client, auth("CUS-DEMO-01"),
              ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0006"})
    assert r["audit"]["rule_id"] == "R1"


def test_fraude_con_gold_bloquea_y_hace_handoff(client, auth):
    h = auth("CUS-DEMO-03")
    r = _chat(client, h, message="Não reconheço uma compra de 3.500")
    assert r["audit"]["rule_id"] == "R7"
    for _ in range(2):   # confirmar bloqueo, luego confirmar caso
        r = _chat(client, h, conversation_id=r["conversation_id"], ui_action={
            "type": "confirm", "pending_action_id": r["ui"]["pending_action"]["pending_action_id"]})
    assert r["state"] == "HANDOFF"
    pkg = next(iter(store.handoffs.values()))
    assert pkg.customer.segment == "Premium"                     # perfil leído de gold
    assert [a.status for a in pkg.actions_taken] == ["verified", "verified"]


def test_score_nulo_en_gold_dispara_R8(client, auth):
    r = _chat(client, auth("CUS-DEMO-02"),
              ui_action={"type": "select_transaction", "transaction_id": "TX-DEMO-0005"})
    assert r["audit"]["rule_id"] == "R8"
