"""Request and response models for the incident register."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Basel II level 1 operational risk event types."""

    INTERNAL_FRAUD = "internal_fraud"
    EXTERNAL_FRAUD = "external_fraud"
    EMPLOYMENT_PRACTICES = "employment_practices_workplace_safety"
    CLIENTS_PRODUCTS = "clients_products_business_practices"
    PHYSICAL_ASSETS = "damage_to_physical_assets"
    SYSTEMS = "business_disruption_system_failures"
    EXECUTION = "execution_delivery_process_management"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentIn(BaseModel):
    """What a person reports. Everything else is derived."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    business_unit: str = Field(min_length=2, max_length=100)
    event_date: date
    gross_loss_aud: float = Field(default=0, ge=0, le=1e12)
    customer_impact: bool = False
    regulatory_breach: bool = False


class Classification(BaseModel):
    event_type: EventType
    method: str  # "rules" or "claude"
    rationale: str


class Incident(IncidentIn):
    id: str
    created_at: datetime
    event_type: EventType
    classification_method: str
    classification_rationale: str
    severity: Severity
    severity_reasons: list[str]


class Summary(BaseModel):
    total_incidents: int
    total_gross_loss_aud: float
    by_event_type: dict[EventType, int]
    by_severity: dict[Severity, int]
