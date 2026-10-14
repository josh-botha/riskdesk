from types import SimpleNamespace

import anthropic
import httpx

from app.classify import ClaudeClassifier, RulesClassifier, _ClaudeAnswer
from app.models import EventType, IncidentIn

INCIDENT = IncidentIn(
    title="Card fraud", description="Cards were cloned at a skimming device in a branch ATM.",
    business_unit="Retail", event_date="2026-10-01",
)


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def classifier(messages):
    return ClaudeClassifier(SimpleNamespace(messages=messages), "claude-opus-5-5", RulesClassifier())


def test_uses_claude_answer_with_structured_output():
    answer = _ClaudeAnswer(event_type=EventType.EXTERNAL_FRAUD, rationale="third-party card skimming")
    messages = FakeMessages(SimpleNamespace(parsed_output=answer, stop_reason="end_turn"))
    result = classifier(messages).classify(INCIDENT)
    assert result.event_type == EventType.EXTERNAL_FRAUD
    assert result.method == "claude"
    assert messages.calls[0]["output_format"] is _ClaudeAnswer


def test_falls_back_to_rules_on_api_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=request)
    result = classifier(FakeMessages(error=error)).classify(INCIDENT)
    assert result.method == "rules"
    assert result.event_type == EventType.EXTERNAL_FRAUD


def test_falls_back_to_rules_on_refusal():
    messages = FakeMessages(SimpleNamespace(parsed_output=None, stop_reason="refusal"))
    assert classifier(messages).classify(INCIDENT).method == "rules"
