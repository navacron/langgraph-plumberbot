"""Test the RAG knowledge base.

Runs with either backend:
  - OPENAI_API_KEY set  → semantic vector search (text-embedding-3-small)
  - Anthropic key only  → BM25 keyword search (no extra key needed)

All tests pass in both modes. The BM25 backend is the default when OPENAI_API_KEY is absent.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Require at least ANTHROPIC_API_KEY (BM25 works without OpenAI)
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping RAG tests",
)


@pytest.fixture(scope="module")
def tools():
    from plumberbot.knowledge import get_retriever
    get_retriever()  # build on first call (vector or BM25)
    from plumberbot.tools.knowledge import knowledge_tools
    return {t.name: t for t in knowledge_tools}


def test_list_articles(tools):
    result = tools["list_articles"].invoke({})
    assert isinstance(result, list)
    expected = {
        "burst_pipe_emergency",
        "drain_cleaning_tips",
        "fix_a_sink",
        "fix_a_toilet",
        "fix_a_water_heater",
    }
    assert set(result) == expected, f"Got: {set(result)}"


def test_search_returns_results(tools):
    result = tools["search_knowledge_base"].invoke({"query": "how to fix a running toilet"})
    assert isinstance(result, str)
    assert len(result) > 50
    # Should mention toilet-related content
    assert "toilet" in result.lower() or "flapper" in result.lower()


def test_search_drain_tips(tools):
    result = tools["search_knowledge_base"].invoke({"query": "baking soda vinegar drain clog"})
    assert "baking soda" in result.lower() or "drain" in result.lower()


def test_search_water_heater(tools):
    result = tools["search_knowledge_base"].invoke({"query": "no hot water pilot light reset"})
    assert "water heater" in result.lower() or "pilot" in result.lower()


def test_search_burst_pipe_emergency(tools):
    result = tools["search_knowledge_base"].invoke({"query": "burst pipe main shut off valve"})
    assert "shut" in result.lower() or "valve" in result.lower() or "burst" in result.lower()


def test_search_no_match_returns_string(tools):
    result = tools["search_knowledge_base"].invoke({"query": "quantum computing blockchain nft"})
    assert isinstance(result, str)
    # May return low-relevance chunks — just ensure it doesn't crash
