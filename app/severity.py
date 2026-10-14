"""Severity scoring.

Deliberately rules-based: a risk team needs to explain every rating, so each step
that moves the rating is recorded as a reason.
"""

from .models import IncidentIn, Severity

ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

# Gross loss bands in AUD (lower bound inclusive).
LOSS_BANDS = [
    (1_000_000, Severity.CRITICAL),
    (100_000, Severity.HIGH),
    (10_000, Severity.MEDIUM),
    (0, Severity.LOW),
]


def score_severity(incident: IncidentIn) -> tuple[Severity, list[str]]:
    level = next(sev for floor, sev in LOSS_BANDS if incident.gross_loss_aud >= floor)
    reasons = [f"gross loss ${incident.gross_loss_aud:,.0f} AUD -> {level}"]

    index = ORDER.index(level)
    if incident.customer_impact:
        index += 1
        reasons.append("customers affected: +1 level")
    if incident.regulatory_breach:
        index += 1
        reasons.append("possible regulatory breach: +1 level")

    final = ORDER[min(index, len(ORDER) - 1)]
    if index >= len(ORDER):
        reasons.append("capped at critical")
    return final, reasons
