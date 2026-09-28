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
