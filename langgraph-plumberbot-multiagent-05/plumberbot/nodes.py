"""Outer graph nodes: identity verification, memory load/save, human input interrupt."""

from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from .db import get_db_connection, run_query
from .llm import llm
from .state import PlumberState


class _PhoneExtraction(BaseModel):
    phone_number: str = Field(
        description="The customer's phone number exactly as written, or empty string if none found"
    )


_structured_llm = llm.with_structured_output(_PhoneExtraction)


def verify_customer(state: PlumberState) -> dict:
    """Extract phone from the customer's message and look up their account."""
    if state.get("customer_id") is not None:
        return {}

    messages = state["messages"]
    latest = messages[-1]
    latest_content = latest.content if hasattr(latest, "content") else str(latest)

    extraction = _structured_llm.invoke([
        SystemMessage(content="Extract the phone number from this message. Return empty string if none."),
        HumanMessage(content=latest_content),
    ])

    if extraction.phone_number:
        rows = run_query(
            "SELECT customer_id, name FROM customers WHERE phone = ?",
            (extraction.phone_number,),
        )
        if rows:
            cust = rows[0]
            return {
                "customer_id": cust["customer_id"],
                "messages": [AIMessage(
                    content=f"Welcome back, {cust['name']}! I've verified your account. How can I help you today?"
                )],
            }

    # No phone found or phone not in DB — prompt the customer
    response = llm.invoke([
        SystemMessage(content=(
            "You are a PlumberBot agent. Your only job right now is account verification. "
            "Ask the customer for their phone number (the one on their account) in one short sentence. "
            "If they just provided a phone number that wasn't found, tell them it wasn't found "
            "and ask them to double-check it. Do NOT address their actual request yet."
        )),
        *messages,
    ])
    return {"messages": [response]}


def human_input(state: PlumberState) -> dict:
    """No-op interrupt node — pauses the graph and waits for user input."""
    user_input = interrupt("Waiting for customer input.")
    return {"messages": [HumanMessage(content=user_input)]}


def should_interrupt(state: PlumberState) -> str:
    return "continue" if state.get("customer_id") is not None else "interrupt"


def load_memory(state: PlumberState) -> dict:
    """Load customer preferences and service history from customer_profile table."""
    customer_id = state["customer_id"]
    rows = run_query(
        "SELECT preferences, service_history FROM customer_profile WHERE customer_id = ?",
        (customer_id,),
    )
    if rows and (rows[0].get("preferences") or rows[0].get("service_history")):
        row = rows[0]
        memory = (
            f"Preferences: {row['preferences'] or 'none'} | "
            f"Service history: {row['service_history'] or 'none'}"
        )
    else:
        memory = ""
    return {"loaded_memory": memory}


class _CustomerMemory(BaseModel):
    preferences: str = Field(
        description="Updated customer preferences (appointment times, plumber preference, etc.). Max 100 words."
    )
    service_history: str = Field(
        description="Brief summary of services discussed or requested in this conversation. Max 100 words."
    )


def save_memory(state: PlumberState) -> dict:
    """Extract insights from the conversation and upsert customer_profile."""
    customer_id = state["customer_id"]
    if customer_id is None or len(state["messages"]) < 3:
        return {}

    try:
        existing = state.get("loaded_memory", "")
        structured = llm.with_structured_output(_CustomerMemory)

        conversation_snippet = "\n".join(
            f"{m.type}: {m.content}"
            for m in state["messages"][-12:]
            if hasattr(m, "content") and m.content and m.type in ("human", "ai")
        )

        memory = structured.invoke([
            SystemMessage(content=(
                "Analyze this customer service conversation. Extract or update:\n"
                "1. Customer preferences (e.g. preferred appointment times, preferred plumber)\n"
                "2. Service history summary (what issues or services came up)\n\n"
                f"Existing profile: {existing or 'none'}\n\n"
                "Keep each field under 100 words. If nothing new to add, preserve existing values."
            )),
            HumanMessage(content=f"Conversation:\n{conversation_snippet}"),
        ])

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO customer_profile (customer_id, preferences, service_history, last_updated)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(customer_id) DO UPDATE SET
                preferences     = excluded.preferences,
                service_history = excluded.service_history,
                last_updated    = excluded.last_updated
            """,
            (customer_id, memory.preferences, memory.service_history),
        )
        conn.commit()
    except Exception:
        pass  # memory save is non-critical

    return {}
