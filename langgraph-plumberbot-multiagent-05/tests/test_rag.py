"""Test the RAG knowledge base without an API key.

These tests verify:
- All 5 articles load and chunk correctly
- list_articles() returns expected filenames
- search_knowledge_base() returns relevant chunks for known queries

Requires OPENAI_API_KEY to build the vectorstore (embeddings are called once on import).
Skip this file if the key is not set.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Skip the entire module if OPENAI_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping RAG tests",
)


@pytest.fixture(scope="module")
def tools():
    # Force vectorstore to build (makes OpenAI embeddings call)
    from plumberbot.knowledge import get_vectorstore
    get_vectorstore()
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
