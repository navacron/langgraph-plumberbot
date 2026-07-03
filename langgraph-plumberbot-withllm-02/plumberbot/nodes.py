"""LangGraph nodes — all classification and response generation uses Claude.

Classification uses structured output (JSON schema) so the result is always
machine-readable. Response generation uses plain text. The interrupt/resume
pattern is identical to bare-01; only the content of messages changes.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field
from langgraph.types import interrupt

from .llm import client, MODEL
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
    """Ask Claude to classify the message into emergency / general / missing_info.

    Uses structured JSON output + adaptive thinking so the model reasons
    carefully before committing to a category.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": state["customer_message"]}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["emergency", "general", "missing_info"],
                        },
                        "urgency_reason": {"type": "string"},
                        "missing_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["category", "urgency_reason", "missing_fields"],
                    "additionalProperties": False,
                },
            }
        },
    )
    text_block = next(b for b in response.content if b.type == "text")
    data = json.loads(text_block.text)
    return {
        "category": data["category"],
        "urgency_reason": data.get("urgency_reason", ""),
        "missing_fields": data.get("missing_fields", []),
    }


def route_request(state: PlumberState) -> str:
    """Conditional edge: map the category to the next node name.

    This function is pure (no LLM) — LangGraph calls it to pick the branch
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
    """Use Claude to generate a friendly question, then pause for the reply.

    LangGraph concept: INTERRUPT
    interrupt() checkpoints the graph state and pauses execution.
    The CLI resumes the graph with Command(resume=<customer reply>).
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=ASK_INFO_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Customer message: {state['customer_message']}\n"
                f"Missing information: {state['missing_fields']}"
            ),
        }],
    )
    question = response.content[0].text

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

    Uses client.messages.parse() with a Pydantic model for reliable
    structured extraction, then generates a warm confirmation message.
    """
    extraction = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system="Extract customer contact and issue details. Be generous — capture whatever is provided.",
        messages=[{"role": "user", "content": state["customer_reply"]}],
        output_format=CustomerProfile,
    )
    data: CustomerProfile = extraction.parsed_output

    profile = {
        "status": "saved",
        "name": data.name,
        "phone": data.phone,
        "address": data.address,
        "issue": data.issue_description,
        "water_leaking": data.water_actively_leaking,
    }

    confirmation = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system="You are a friendly PlumberBot customer service agent.",
        messages=[{
            "role": "user",
            "content": (
                f"We saved the customer's profile: {profile}. "
                "Write a warm 2-sentence confirmation and say a plumber "
                "will be in touch shortly."
            ),
        }],
    )
    return {
        "profile": profile,
        "final_response": confirmation.content[0].text,
    }


def answer_faq(state: PlumberState) -> dict:
    """Use Claude to answer a general or FAQ question."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=FAQ_SYSTEM,
        messages=[{"role": "user", "content": state["customer_message"]}],
    )
    return {"final_response": response.content[0].text}


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
    """Create a dispatch ticket (if approved) and generate an LLM response."""
    decision = state["human_decision"]

    ticket: dict = {}
    if decision == "approve":
        ticket = {
            "ticket_id": "PLUMB-001",
            "status": "created",
            "source": "LangGraph withllm-02",
        }

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=TICKET_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Dispatcher decision: {decision}\n"
                f"Customer message: {state['customer_message']}\n"
                f"Urgency reason: {state['urgency_reason']}\n"
                f"Ticket: {ticket if ticket else 'none created'}\n\n"
                "Write a brief professional response to the customer."
            ),
        }],
    )
    return {
        "ticket": ticket,
        "final_response": response.content[0].text,
    }
