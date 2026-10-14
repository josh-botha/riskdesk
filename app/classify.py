"""Classify an incident into a Basel II event type.

The rules classifier always works and costs nothing. The Claude classifier is used
only when ANTHROPIC_API_KEY is set, and falls back to the rules on any failure, so
a model outage or refusal never blocks someone logging an incident.
"""

import logging
import re
from typing import Protocol

import anthropic
from pydantic import BaseModel

from .models import Classification, EventType, IncidentIn

log = logging.getLogger(__name__)

# A trailing * marks a stem ("hack*" matches hacked, hacker); anything else must
# match as a whole word, so "fire" does not match "fired".
KEYWORDS: dict[EventType, list[str]] = {
    EventType.INTERNAL_FRAUD: [
        "embezzl*", "misappropriat*", "unauthorised trading", "unauthorized trading",
        "rogue trader", "insider trading", "employee fraud", "staff fraud", "collusion",
        "kickback*", "falsified",
    ],
    EventType.EXTERNAL_FRAUD: [
        "phishing", "scam*", "hack*", "malware", "ransomware", "cyber*", "forged",
        "counterfeit", "skimming", "identity theft", "account takeover", "external fraud",
        "impersonat*",
    ],
    EventType.EMPLOYMENT_PRACTICES: [
        "injur*", "workplace safety", "harassment", "discriminat*", "unfair dismissal",
        "whs", "slipped", "bullying",
    ],
    EventType.CLIENTS_PRODUCTS: [
        "mis-sold", "mis-selling", "missold", "suitability", "privacy breach",
        "breach of privacy", "complaint*", "fiduciary", "aml", "sanctions",
        "market manipulation", "conflict of interest", "responsible lending",
    ],
    EventType.PHYSICAL_ASSETS: [
        "fire", "flood*", "storm", "earthquake", "vandal*", "terroris*", "building damage",
    ],
    EventType.SYSTEMS: [
        "outage*", "system failure", "downtime", "network", "server*", "software bug",
        "power failure", "unavailable", "crash*", "latency", "degraded",
    ],
    EventType.EXECUTION: [
        "data entry", "payment error", "reconciliation", "settlement", "wrong account",
        "missed deadline", "manual error", "vendor*", "duplicate payment", "incorrect*",
        "keying error", "processing error",
    ],
}


def _pattern(keyword: str) -> re.Pattern:
    if keyword.endswith("*"):
        return re.compile(rf"\b{re.escape(keyword[:-1])}\w*")
    return re.compile(rf"\b{re.escape(keyword)}\b")


PATTERNS = {
    event_type: [(kw.rstrip("*"), _pattern(kw)) for kw in words]
    for event_type, words in KEYWORDS.items()
}


class Classifier(Protocol):
    def classify(self, incident: IncidentIn) -> Classification: ...


class RulesClassifier:
    """Keyword scoring. Ties and no-match default to execution/process failure,
    the most common Basel category for everyday operational errors."""

    def classify(self, incident: IncidentIn) -> Classification:
        text = f"{incident.title} {incident.description}".lower()
        scores = {
            event_type: [kw for kw, pattern in patterns if pattern.search(text)]
            for event_type, patterns in PATTERNS.items()
        }
        best = max(scores, key=lambda et: len(scores[et]))
        matched = scores[best]
        if not matched:
            return Classification(
                event_type=EventType.EXECUTION,
                method="rules",
                rationale="no category keywords matched; defaulted to execution/process",
            )
        return Classification(
            event_type=best,
            method="rules",
            rationale=f"matched: {', '.join(matched)}",
        )


class _ClaudeAnswer(BaseModel):
    event_type: EventType
    rationale: str


SYSTEM_PROMPT = """You classify operational risk incidents for a bank's non-financial risk team.
Assign exactly one Basel II level 1 event type:
- internal_fraud: losses from acts by staff intended to defraud or circumvent policy
- external_fraud: losses from acts by third parties intended to defraud or steal, including cyber attacks
- employment_practices_workplace_safety: employment law, health and safety, discrimination
- clients_products_business_practices: failing obligations to clients, product flaws, conduct, privacy, AML
- damage_to_physical_assets: natural disasters, fire, vandalism and other physical damage
- business_disruption_system_failures: system outages, software or hardware failures, utility outages
- execution_delivery_process_management: failed transaction processing or process management,
  including errors by vendors

Give a one-sentence rationale a risk analyst could check against the description."""


class ClaudeClassifier:
    def __init__(self, client: anthropic.Anthropic, model: str, fallback: Classifier):
        self.client = client
        self.model = model
        self.fallback = fallback

    def classify(self, incident: IncidentIn) -> Classification:
        prompt = (
            f"Title: {incident.title}\n"
            f"Business unit: {incident.business_unit}\n"
            f"Description: {incident.description}"
        )
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                output_format=_ClaudeAnswer,
            )
        except anthropic.APIError as exc:
            log.warning("Claude classification failed, using rules: %s", exc)
            return self.fallback.classify(incident)

        answer = response.parsed_output
        if response.stop_reason == "refusal" or answer is None:
            log.warning("Claude returned no usable answer (%s), using rules", response.stop_reason)
            return self.fallback.classify(incident)

        return Classification(
            event_type=answer.event_type, method="claude", rationale=answer.rationale
        )
