"""Scheduling subagent — built from scratch to show the manual ReAct pattern.

This mirrors Part 1.1 of the 201/multi_agent.ipynb notebook: an LLM node
+ ToolNode + conditional edge, wired into a StateGraph by hand.

Compare with agents/dispatch.py and agents/knowledge.py which use the
create_react_agent shortcut (notebook Part 1.2).  Both compile to the same
underlying graph — this version just makes the internals explicit.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

from ..llm import llm
from ..state import InputState, PlumberState
from ..tools.scheduling import scheduling_tools

_PROMPT = """\
You are the scheduling specialist for PlumberBot, a professional plumbing company.

Help verified customers with:
- Viewing their existing appointments
- Looking up available services and pricing
- Finding available plumbers by specialty
- Booking new appointments

The customer has already been verified — their customer_id is automatically injected into \
your tools, so you never need to ask for it.

Be friendly, concise, and action-oriented. Do not handle emergency dispatch or general \
plumbing how-to advice — those are handled by other agents. When you have answered the \
question, stop immediately without asking follow-up questions.
"""

# Bind tools to the LLM once at module load — same instance reused across calls
_llm_with_tools = llm.bind_tools(scheduling_tools)

# ── nodes ──────────────────────────────────────────────────────────────────────

def _scheduling_assistant(state: PlumberState) -> dict:
    """Reasoning node: decide which tool to call (or finish)."""
    memory = state.get("loaded_memory", "")
    system = _PROMPT
    if memory:
        system += f"\n\nCustomer profile (use to personalize your response):\n{memory}"
    response = _llm_with_tools.invoke(
        [SystemMessage(content=system)] + list(state["messages"])
    )
    return {"messages": [response]}


# ToolNode handles InjectedState automatically — it reads PlumberState and
# injects customer_id into any tool parameter annotated with InjectedState("customer_id")
_tool_node = ToolNode(scheduling_tools)

# ── conditional edge ───────────────────────────────────────────────────────────

def _should_continue(state: PlumberState) -> str:
    """Route to tools if the LLM made a tool call, otherwise finish."""
    return "continue" if state["messages"][-1].tool_calls else "end"


# ── graph factory ──────────────────────────────────────────────────────────────

def build_scheduling_subagent():
    """Wire the ReAct loop manually: assistant → tools → assistant → … → END."""
    graph = StateGraph(PlumberState, input=InputState)

    graph.add_node("scheduling_assistant", _scheduling_assistant)
    graph.add_node("tools", _tool_node)

    graph.add_edge(START, "scheduling_assistant")
    graph.add_conditional_edges(
        "scheduling_assistant",
        _should_continue,
        {"continue": "tools", "end": END},
    )
    graph.add_edge("tools", "scheduling_assistant")

    return graph.compile(name="scheduling_subagent")
