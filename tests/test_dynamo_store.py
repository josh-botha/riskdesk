from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from app.models import EventType, Incident, Severity
from app.store import DynamoStore


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-2")
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        yield dynamodb.create_table(
            TableName="riskdesk-test",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )


def make(incident_id, loss):
    return Incident(
        id=incident_id, created_at=datetime.now(UTC), title="Test incident",
        description="Stored and read back through DynamoDB.", business_unit="Ops",
        event_date="2026-10-01", gross_loss_aud=loss, event_type=EventType.SYSTEMS,
        classification_method="rules", classification_rationale="test",
        severity=Severity.MEDIUM, severity_reasons=["test"],
    )


def test_round_trip_keeps_every_field(table):
    store = DynamoStore(table)
    original = make("a1", 12_345.67)
    store.put(original)
    assert store.get("a1") == original
    assert store.get("missing") is None


def test_list_returns_newest_first(table):
    store = DynamoStore(table)
    store.put(make("old", 1))
    store.put(make("new", 2))
    assert [i.id for i in store.list()] == ["new", "old"]
