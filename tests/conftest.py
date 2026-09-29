import os

os.environ.setdefault("OPS_DB_PATH", ":memory:")  # los tests usan una base temporal, no data/ops.sqlite
# Los tests usan SIEMPRE los datos de plástico (stubs), aunque exista data/gold/gold.duckdb.
# (tests/test_gold.py arma su propio gold de prueba y lo prueba aparte.)
os.environ.setdefault("GOLD_DB_PATH", "__tests_sin_gold__.duckdb")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import reset_store


@pytest.fixture
def client():
    reset_store()
    return TestClient(app)


def login(client, customer_id="CUS-DEMO-01"):
    r = client.post("/api/auth/login", json={"customer_id": customer_id, "otp": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return lambda customer_id="CUS-DEMO-01": login(client, customer_id)
