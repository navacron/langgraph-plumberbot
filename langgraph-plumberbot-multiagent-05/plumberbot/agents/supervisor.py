"""Supervisor agent — routes customer requests to specialist subagents.

Subagents are called as tools (not subgraph nodes), following the pattern from the
LangGraph 201 multi-agent notebook. The supervisor synthesizes their responses.
"""

from typing import Annotated, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, create_react_agent

from ..llm import llm
from ..state import PlumberState

_SUPERVISOR_PROMPT = """\
You are the PlumberBot supervisor — the primary customer service agent for a professional \
plumbing company. You manage a team of three specialist subagents:

1. **scheduling_subagent** — books appointments, shows service catalog and pricing, \
   finds available plumbers.
2. **dispatch_subagent** — creates and tracks service tickets, handles emergency dispatch, \
   finds the on-call plumber.
3. **knowledge_subagent** — answers plumbing how-to questions and DIY tips from our \
   knowledge base.

Your job is to:
- Route each part of the customer's request to the right subagent
- Call multiple subagents when a request spans multiple domains
- Synthesize their responses into a single clear, friendly reply

The customer is already verified. Do not handle requests unrelated to plumbing services.
"""


def _make_supervisor_prompt(state: PlumberState) -> list:
    memory = state.get("loaded_memory", "")
    system = _SUPERVISOR_PROMPT
    if memory:
        system += f"\n\nCustomer profile:\n{memory}"
    msgs = list(state["messages"])
    # Anthropic requires the conversation to end with a human message.
    # After verify_customer adds its welcome AIMessage, the state ends with an AI
    # message and no new human request — inject a nudge so the model has a
    # clear human turn to respond to instead of doing message-prefilling.
    if msgs and getattr(msgs[-1], "type", "") != "human":
        msgs = msgs + [HumanMessage(
            content="Please address my plumbing request based on the conversation above."
        )]
    return [SystemMessage(content=system)] + msgs


def build_supervisor():
    from .scheduling import build_scheduling_subagent
    from .dispatch import build_dispatch_subagent
    from .knowledge import build_knowledge_subagent

    _scheduling = build_scheduling_subagent()
    _dispatch = build_dispatch_subagent()
    _knowledge = build_knowledge_subagent()

    @tool
    def call_scheduling_subagent(
        query: str,
        customer_id: Annotated[Optional[int], InjectedState("customer_id")],
        loaded_memory: Annotated[str, InjectedState("loaded_memory")],
    ) -> str:
        """Route to the scheduling subagent for appointments, service catalog, and plumber availability."""
        result = _scheduling.invoke({
            "messages": [HumanMessage(content=query)],
            "customer_id": customer_id,
            "loaded_memory": loaded_memory,
        })
        return result["messages"][-1].content

    @tool
    def call_dispatch_subagent(
        query: str,
        customer_id: Annotated[Optional[int], InjectedState("customer_id")],
        loaded_memory: Annotated[str, InjectedState("loaded_memory")],
    ) -> str:
        """Route to the dispatch subagent for emergency tickets, open tickets, and on-call plumber info."""
        result = _dispatch.invoke({
            "messages": [HumanMessage(content=query)],
            "customer_id": customer_id,
            "loaded_memory": loaded_memory,
        })
        return result["messages"][-1].content

    @tool
    def call_knowledge_subagent(query: str) -> str:
        """Route to the knowledge subagent for plumbing how-to tips and troubleshooting guides."""
        result = _knowledge.invoke({
            "messages": [HumanMessage(content=query)],
            "customer_id": None,
            "loaded_memory": "",
        })
        return result["messages"][-1].content

    return create_react_agent(
        model=llm,
        tools=[call_scheduling_subagent, call_dispatch_subagent, call_knowledge_subagent],
        prompt=_make_supervisor_prompt,
        name="supervisor",
        state_schema=PlumberState,
    )
