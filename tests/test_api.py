from tests.conftest import incident


def test_health_needs_no_key(client):
    client.headers.pop("X-API-Key")
    assert client.get("/health").json() == {"status": "ok"}


def test_incident_endpoints_reject_a_missing_or_wrong_key(client):
    assert client.get("/incidents", headers={"X-API-Key": "wrong"}).status_code == 401
    client.headers.pop("X-API-Key")
    assert client.post("/incidents", json=incident()).status_code == 401


def test_create_classifies_and_scores(client):
    response = client.post("/incidents", json=incident())
    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "business_disruption_system_failures"
    assert body["severity"] == "high"  # medium loss band, +1 for customer impact
    assert body["classification_method"] == "rules"


def test_invalid_input_is_rejected(client):
    assert client.post("/incidents", json=incident(gross_loss_aud=-5)).status_code == 422
    assert client.post("/incidents", json=incident(title="")).status_code == 422


def test_get_by_id_and_404(client):
    created = client.post("/incidents", json=incident()).json()
    assert client.get(f"/incidents/{created['id']}").json() == created
    assert client.get("/incidents/does-not-exist").status_code == 404


def test_filter_and_summary(client):
    client.post("/incidents", json=incident())
    client.post("/incidents", json=incident(
        title="Branch fire", description="A fire damaged the Parramatta branch overnight.",
        gross_loss_aud=250_000, customer_impact=False,
    ))
    fires = client.get("/incidents", params={"event_type": "damage_to_physical_assets"}).json()
    assert [i["title"] for i in fires] == ["Branch fire"]

    summary = client.get("/summary").json()
    assert summary["total_incidents"] == 2
    assert summary["total_gross_loss_aud"] == 275_000
    assert summary["by_severity"] == {"high": 2}
