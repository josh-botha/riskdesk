"""RiskDesk: an operational risk incident register with automatic triage."""

import logging
import os
import secrets
import uuid
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from .classify import Classifier, ClaudeClassifier, RulesClassifier
from .models import EventType, Incident, IncidentIn, Severity, Summary
from .severity import score_severity
from .store import DynamoStore, IncidentStore, MemoryStore

log = logging.getLogger("riskdesk")

app = FastAPI(
    title="RiskDesk",
    version="1.0.0",
    description="Log operational risk incidents; each one is classified into a "
    "Basel II event type and given an explainable severity rating.",
)


@lru_cache
def get_store() -> IncidentStore:
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        return MemoryStore()
    import boto3

    return DynamoStore(boto3.resource("dynamodb").Table(table_name))


@lru_cache
def get_classifier() -> Classifier:
    rules = RulesClassifier()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return rules
    import anthropic

    model = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
    return ClaudeClassifier(anthropic.Anthropic(), model=model, fallback=rules)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Every incident endpoint needs the key when API_KEY is set (always, on AWS)."""
    expected = os.environ.get("API_KEY")
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/incidents",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_incident(
    body: IncidentIn,
    store: IncidentStore = Depends(get_store),
    classifier: Classifier = Depends(get_classifier),
) -> Incident:
    classification = classifier.classify(body)
    severity, reasons = score_severity(body)
    incident = Incident(
        **body.model_dump(),
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        event_type=classification.event_type,
        classification_method=classification.method,
        classification_rationale=classification.rationale,
        severity=severity,
        severity_reasons=reasons,
    )
    store.put(incident)
    log.info("logged incident %s as %s/%s", incident.id, incident.event_type, severity)
    return incident


@app.get("/incidents", dependencies=[Depends(require_api_key)])
def list_incidents(
    event_type: EventType | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    store: IncidentStore = Depends(get_store),
) -> list[Incident]:
    incidents = store.list()
    if event_type:
        incidents = [i for i in incidents if i.event_type == event_type]
    if severity:
        incidents = [i for i in incidents if i.severity == severity]
    return incidents


@app.get("/incidents/{incident_id}", dependencies=[Depends(require_api_key)])
def get_incident(incident_id: str, store: IncidentStore = Depends(get_store)) -> Incident:
    incident = store.get(incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    return incident


@app.get("/summary", dependencies=[Depends(require_api_key)])
def summary(store: IncidentStore = Depends(get_store)) -> Summary:
    incidents = store.list()
    return Summary(
        total_incidents=len(incidents),
        total_gross_loss_aud=round(sum(i.gross_loss_aud for i in incidents), 2),
        by_event_type=dict(Counter(i.event_type for i in incidents)),
        by_severity=dict(Counter(i.severity for i in incidents)),
    )
