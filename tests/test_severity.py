import pytest

from app.models import IncidentIn, Severity
from app.severity import score_severity


def make(loss, customer=False, regulatory=False):
    return IncidentIn(
        title="Test", description="A test incident description.", business_unit="Ops",
        event_date="2026-10-01", gross_loss_aud=loss,
        customer_impact=customer, regulatory_breach=regulatory,
    )


@pytest.mark.parametrize(
    ("loss", "expected"),
    [(0, Severity.LOW), (9_999, Severity.LOW), (10_000, Severity.MEDIUM),
     (100_000, Severity.HIGH), (1_000_000, Severity.CRITICAL)],
)
def test_loss_bands(loss, expected):
    assert score_severity(make(loss))[0] == expected


def test_customer_and_regulatory_impact_each_raise_one_level():
    severity, reasons = score_severity(make(5_000, customer=True, regulatory=True))
    assert severity == Severity.HIGH
    assert len(reasons) == 3


def test_rating_caps_at_critical_and_records_it():
    severity, reasons = score_severity(make(2_000_000, customer=True))
    assert severity == Severity.CRITICAL
    assert reasons[-1] == "capped at critical"
