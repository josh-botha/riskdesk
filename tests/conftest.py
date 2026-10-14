import pytest
from fastapi.testclient import TestClient

from app.classify import RulesClassifier
from app.main import app, get_classifier, get_store
from app.store import MemoryStore

API_KEY = "test-key-0123456789"


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_classifier] = lambda: RulesClassifier()
    with TestClient(app, headers={"X-API-Key": API_KEY}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def incident(**overrides):
    body = {
        "title": "Payments outage",
        "description": "Core payments server crashed and customers could not pay for 40 minutes.",
        "business_unit": "Retail Banking",
        "event_date": "2026-10-01",
        "gross_loss_aud": 25000,
        "customer_impact": True,
        "regulatory_breach": False,
    }
    body.update(overrides)
    return body
