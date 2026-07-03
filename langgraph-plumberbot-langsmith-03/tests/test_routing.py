"""Tests for pure (non-LLM) logic — no API key required.

route_request is a plain function and can be tested in isolation.
LLM-dependent nodes (classify_request, answer_faq, etc.) are integration
tests; they require a real ANTHROPIC_API_KEY and are not included here.
"""

import pytest

from plumberbot.nodes import route_request


def _state(category: str) -> dict:
    return {
        "customer_message": "",
        "category": category,
        "missing_fields": [],
        "urgency_reason": "",
        "human_decision": "",
        "ticket": {},
        "customer_reply": "",
        "profile": {},
        "final_response": "",
    }


def test_route_missing_info():
    assert route_request(_state("missing_info")) == "ask_missing_info"


def test_route_general():
    assert route_request(_state("general")) == "answer_faq"


def test_route_emergency():
    assert route_request(_state("emergency")) == "human_review"


def test_route_unknown_falls_through_to_faq():
    # Any unrecognised category falls through to answer_faq (the else branch)
    assert route_request(_state("unknown")) == "answer_faq"
