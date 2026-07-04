from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from ..llm import llm
from ..state import PlumberState
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


def _make_prompt(state: PlumberState) -> list:
    memory = state.get("loaded_memory", "")
    system = _PROMPT
    if memory:
        system += f"\n\nCustomer profile (use to personalize your response):\n{memory}"
    return [SystemMessage(content=system)] + list(state["messages"])


def build_scheduling_subagent():
    return create_react_agent(
        model=llm,
        tools=scheduling_tools,
        prompt=_make_prompt,
        name="scheduling_subagent",
        state_schema=PlumberState,
    )
