import pytest

from app.classify import RulesClassifier
from app.models import EventType, IncidentIn


def make(title, description):
    return IncidentIn(
        title=title, description=description, business_unit="Ops", event_date="2026-10-01"
    )


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Phishing loss", "Customer lost funds after a phishing email impersonating the bank.", EventType.EXTERNAL_FRAUD),
        ("Trader breach", "A trader embezzled client funds through unauthorised trading.", EventType.INTERNAL_FRAUD),
        ("Branch fire", "A kitchen fire damaged the branch and closed it for a week.", EventType.PHYSICAL_ASSETS),
        ("Online banking down", "Online banking outage after a failed server patch.", EventType.SYSTEMS),
        ("Duplicate run", "Batch job made a duplicate payment to 300 suppliers.", EventType.EXECUTION),
        ("Mis-selling", "Product was mis-sold to customers who failed the suitability test.", EventType.CLIENTS_PRODUCTS),
        ("Warehouse injury", "Contractor was injured lifting archive boxes.", EventType.EMPLOYMENT_PRACTICES),
    ],
)
def test_rules_pick_the_basel_event_type(title, description, expected):
    result = RulesClassifier().classify(make(title, description))
    assert result.event_type == expected
    assert result.method == "rules"


def test_whole_words_only_so_fired_is_not_fire():
    result = RulesClassifier().classify(make("Dismissal", "The manager fired a team member without process."))
    assert result.event_type != EventType.PHYSICAL_ASSETS


def test_no_keywords_defaults_to_execution_and_says_so():
    result = RulesClassifier().classify(make("Odd one", "Something unusual happened in the office today."))
    assert result.event_type == EventType.EXECUTION
    assert "defaulted" in result.rationale
