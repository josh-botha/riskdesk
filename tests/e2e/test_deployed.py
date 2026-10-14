"""Runs against a live deployment (CI runs it after every deploy).

    BASE_URL=https://xxxx.lambda-url.ap-southeast-2.on.aws API_KEY=... pytest tests/e2e
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="BASE_URL not set")


@pytest.fixture
def api():
    with httpx.Client(base_url=BASE_URL, headers={"X-API-Key": os.environ["API_KEY"]}, timeout=30) as client:
        yield client


def test_deployed_service_round_trip(api):
    assert api.get("/health").json() == {"status": "ok"}
    created = api.post("/incidents", json={
        "title": "E2E check",
        "description": "Automated end-to-end check after deploy: a reconciliation break was found.",
        "business_unit": "Technology",
        "event_date": "2026-10-14",
        "gross_loss_aud": 0,
    })
    assert created.status_code == 201
    assert api.get(f"/incidents/{created.json()['id']}").status_code == 200


def test_deployed_service_rejects_requests_without_a_key():
    assert httpx.get(f"{BASE_URL}/incidents", timeout=30).status_code == 401
