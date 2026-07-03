"""LangGraph nodes — all classification and response generation uses Claude.

Follows the same patterns as langchain-academy:
  - ChatAnthropic via langchain-anthropic
  - llm.invoke([SystemMessage(...), HumanMessage(...)])
  - llm.with_structured_output(PydanticModel) for structured extraction
  - response.content for the reply text
"""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from .llm import llm
from .state import PlumberState


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class Classification(BaseModel):
    category: Literal["emergency", "general", "missing_info"]
    urgency_reason: str = Field(default="")
    missing_fields: list[str] = Field(default_factory=list)


class CustomerProfile(BaseModel):
    name: str = Field(default="Unknown")
    phone: str = Field(default="not provided")
    address: str = Field(default="not provided")
    issue_description: str = Field(default="")
    water_actively_leaking: bool = Field(default=False)


# ── System prompts ────────────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """\
You are a dispatcher for a professional plumbing company.

Classify the customer message into exactly one of three categories:

  emergency    — Situation needs immediate dispatch: flooding, burst pipes,
                 sewer overflow, major leak, or no water supply.
                 ONLY classify as emergency if the customer has provided
                 their address or location.

  general      — Customer is asking a general question about services,
                 pricing, or availability.

  missing_info — Message lacks enough information to act on: no address for a
                 service request, too vague to triage, or an urgent situation
                 without a location.

Rules:
- Urgent situation WITHOUT address → missing_info  (will ask for address)
- Question about services/pricing  → general
- Clear emergency WITH address     → emergency\
"""

ASK_INFO_SYSTEM = """\
You are a caring customer service agent for PlumberBot, a plumbing company.

Write a warm, concise reply (3-4 sentences) asking the customer for:
  • Full address
  • Phone number
  • Brief description of the issue
  • Whether water is actively leaking or flooding right now

Be empathetic. Mention that you want to dispatch help quickly.\
"""

FAQ_SYSTEM = """\
You are a friendly, knowledgeable customer service agent for PlumberBot.

Services: leaks, clogged drains, water heaters (install & repair),
sewer backups, emergency plumbing (burst pipes, flooding).
Phone: (555) 123-4567  |  Hours: 24/7 emergency, 8am-6pm regular.

Answer the customer's question helpfully and concisely (2-4 sentences).
Close by inviting them to call or share their address to book a visit.\
"""

TICKET_SYSTEM = """\
You are a professional customer service agent for PlumberBot.
Write a brief professional response to the customer based on the
dispatcher's decision. Keep it to 2-3 sentences.\
"""


# ── Nodes ─────────────────────────────────────────────────────────────────────

def classify_request(state: PlumberState) -> dict:
    """Classify the message using structured output — same pattern as langchain-academy."""
    structured_llm = llm.with_structured_output(Classification)
    result: Classification = structured_llm.invoke([
        SystemMessage(content=CLASSIFY_SYSTEM),
        HumanMessage(content=state["customer_message"]),
    ])
    return {
        "category": result.category,
        "urgency_reason": result.urgency_reason,
        "missing_fields": result.missing_fields,
    }


def route_request(state: PlumberState) -> str:
    """Conditional edge: map the category to the next node name.

    Pure function — no LLM. LangGraph calls this to pick the branch
    after classify_request finishes.
    """
    category = state["category"]
    if category == "missing_info":
        return "ask_missing_info"
    elif category == "emergency":
        return "human_review"
    else:
        return "answer_faq"


def ask_missing_info(state: PlumberState) -> dict:
    """Generate a friendly question with Claude, then pause for the reply.

    LangGraph concept: INTERRUPT
    interrupt() checkpoints the graph state and pauses execution.
    The CLI resumes the graph with Command(resume=<customer reply>).
    """
    response = llm.invoke([
        SystemMessage(content=ASK_INFO_SYSTEM),
        HumanMessage(content=(
            f"Customer message: {state['customer_message']}\n"
            f"Missing information: {state['missing_fields']}"
        )),
    ])
    question = response.content

    reply = interrupt({
        "bot_message": question,
        "instructions": (
            "Reply with your address, phone number, issue description, "
            "and whether water is actively leaking."
        ),
    })
    return {"final_response": question, "customer_reply": reply}


def save_profile(state: PlumberState) -> dict:
    """Extract a structured profile from the customer's reply, then confirm.

    Uses with_structured_output(CustomerProfile) for reliable extraction —
    same pattern as langchain-academy's research_assistant analysts generation.
    """
    structured_llm = llm.with_structured_output(CustomerProfile)
    data: CustomerProfile = structured_llm.invoke([
        SystemMessage(content="Extract customer contact and issue details. Be generous — capture whatever is provided."),
        HumanMessage(content=state["customer_reply"]),
    ])

    profile = {
        "status": "saved",
        "name": data.name,
        "phone": data.phone,
        "address": data.address,
        "issue": data.issue_description,
        "water_leaking": data.water_actively_leaking,
    }

    confirmation = llm.invoke([
        SystemMessage(content="You are a friendly PlumberBot customer service agent."),
        HumanMessage(content=(
            f"We saved the customer's profile: {profile}. "
            "Write a warm 2-sentence confirmation and say a plumber "
            "will be in touch shortly."
        )),
    ])
    return {
        "profile": profile,
        "final_response": confirmation.content,
    }


def answer_faq(state: PlumberState) -> dict:
    """Answer a general or FAQ question with Claude."""
    response = llm.invoke([
        SystemMessage(content=FAQ_SYSTEM),
        HumanMessage(content=state["customer_message"]),
    ])
    return {"final_response": response.content}


def human_review(state: PlumberState) -> dict:
    """Pause for dispatcher approval — no LLM involved.

    LangGraph concept: INTERRUPT
    Same pattern as bare-01: the graph freezes here until the CLI resumes it.
    """
    decision = interrupt({
        "message": "Emergency plumbing dispatch requires approval",
        "customer_message": state["customer_message"],
        "urgency_reason": state["urgency_reason"],
        "options": ["approve", "reject", "escalate"],
    })
    return {"human_decision": decision}


def create_ticket(state: PlumberState) -> dict:
    """Create a dispatch ticket (if approved) and generate a Claude response."""
    decision = state["human_decision"]

    ticket: dict = {}
    if decision == "approve":
        ticket = {
            "ticket_id": "PLUMB-001",
            "status": "created",
            "source": "LangGraph withllm-02",
        }

    response = llm.invoke([
        SystemMessage(content=TICKET_SYSTEM),
        HumanMessage(content=(
            f"Dispatcher decision: {decision}\n"
            f"Customer message: {state['customer_message']}\n"
            f"Urgency reason: {state['urgency_reason']}\n"
            f"Ticket: {ticket if ticket else 'none created'}\n\n"
            "Write a brief professional response to the customer."
        )),
    ])
    return {
        "ticket": ticket,
        "final_response": response.content,
    }
