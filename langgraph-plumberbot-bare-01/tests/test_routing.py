"""Unit tests for the classification and routing logic.

These tests exercise the node functions in isolation — no graph invocation
or checkpointer required. This keeps tests fast and dependency-free.
"""

import sys
import os

# Make the package importable when running pytest from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plumberbot.nodes import classify_request, route_request
from plumberbot.state import PlumberState


def make_state(message: str) -> PlumberState:
    return PlumberState(
        customer_message=message,
        category="",
        missing_fields=[],
        urgency_reason="",
        human_decision="",
        ticket={},
        customer_reply="",
        profile={},
        final_response="",
    )


# ---------------------------------------------------------------------------
# classify_request tests
# ---------------------------------------------------------------------------

class TestClassifyRequest:
    def test_emergency_with_address(self):
        state = make_state("My basement is flooding from a burst pipe. I am at 22 Oak Street.")
        result = classify_request(state)
        assert result["category"] == "emergency"
        assert result["missing_fields"] == []
        assert "urgency_reason" in result
        assert result["urgency_reason"] != ""

    def test_missing_info_no_address(self):
        state = make_state("My sink is leaking.")
        result = classify_request(state)
        assert result["category"] == "missing_info"
        assert len(result["missing_fields"]) > 0

    def test_general_question(self):
        state = make_state("Do you fix water heaters?")
        result = classify_request(state)
        assert result["category"] == "general"
        assert result["missing_fields"] == []

    def test_emergency_without_location_becomes_missing_info(self):
        state = make_state("There is flooding in my home!")
        result = classify_request(state)
        assert result["category"] == "missing_info"
        assert "address" in result["missing_fields"]

    def test_burst_pipe_with_street_number(self):
        state = make_state("Burst pipe at 5 Maple Ave, water everywhere.")
        result = classify_request(state)
        assert result["category"] == "emergency"


# ---------------------------------------------------------------------------
# route_request tests
# ---------------------------------------------------------------------------

class TestRouteRequest:
    def _state_with_category(self, category: str) -> PlumberState:
        s = make_state("test message")
        s["category"] = category
        return s

    def test_routes_missing_info(self):
        state = self._state_with_category("missing_info")
        assert route_request(state) == "ask_missing_info"

    def test_routes_emergency(self):
        state = self._state_with_category("emergency")
        assert route_request(state) == "human_review"

    def test_routes_general(self):
        state = self._state_with_category("general")
        assert route_request(state) == "answer_faq"
