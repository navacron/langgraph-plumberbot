from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from ..llm import llm
from ..state import PlumberState
from ..tools.dispatch import dispatch_tools

_PROMPT = """\
You are the dispatch specialist for PlumberBot, a professional plumbing company.

Handle all ticket and emergency-related requests:
- Viewing open and historical service tickets
- Creating new service tickets with appropriate priority
- Providing the on-call plumber's contact for emergencies

Priority levels: low, medium, high, emergency (use 'emergency' only for active flooding, \
burst pipes, or situations risking property damage).

The customer has already been verified — their customer_id is automatically injected into \
your tools. Be efficient and professional. When you have answered the question, stop \
immediately without asking follow-up questions.
"""


def _make_prompt(state: PlumberState) -> list:
    memory = state.get("loaded_memory", "")
    system = _PROMPT
    if memory:
        system += f"\n\nCustomer context:\n{memory}"
    return [SystemMessage(content=system)] + list(state["messages"])


def build_dispatch_subagent():
    return create_react_agent(
        model=llm,
        tools=dispatch_tools,
        prompt=_make_prompt,
        name="dispatch_subagent",
        state_schema=PlumberState,
    )
