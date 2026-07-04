"""Outer graph nodes: identity verification, new-customer registration, memory load/save."""

from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from .db import get_db_connection, run_query
from .llm import llm
from .state import PlumberState


# ── Structured-output helpers ─────────────────────────────────────────────────

class _PhoneExtraction(BaseModel):
    phone_number: str = Field(
        description="The customer's phone number exactly as written, or empty string if none found"
    )

class _NameExtraction(BaseModel):
    name: str = Field(
        description="The customer's full name (first + last), or empty string if not clearly stated"
    )

class _Confirmation(BaseModel):
    confirmed: bool = Field(
        description="True if the user said yes / confirmed / ok / correct, False for no / cancel / decline"
    )

_phone_llm = llm.with_structured_output(_PhoneExtraction)
_name_llm  = llm.with_structured_output(_NameExtraction)
_confirm_llm = llm.with_structured_output(_Confirmation)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_ticket_summary(customer_id: int) -> str:
    """Return a formatted list of open tickets, or empty string if none."""
    rows = run_query(
        "SELECT ticket_id, description, priority FROM tickets "
        "WHERE customer_id = ? AND status = 'open' ORDER BY created_at DESC",
        (customer_id,),
    )
    if not rows:
        return ""
    lines = "\n".join(
        f"  • Ticket #{t['ticket_id']}: "
        f"{t['description'][:70]}{'...' if len(t['description']) > 70 else ''} "
        f"({t['priority']} priority)"
        for t in rows
    )
    n = len(rows)
    return f"\n\nYou have {n} open ticket{'s' if n > 1 else ''}:\n{lines}"


def _extract_phone(text: str) -> str:
    return _phone_llm.invoke([
        SystemMessage(content="Extract the phone number from this message exactly as written. Return empty string if none."),
        HumanMessage(content=text),
    ]).phone_number


def _extract_name(text: str) -> str:
    return _name_llm.invoke([
        SystemMessage(content="Extract the customer's full name from this message. Return empty string if not clearly provided."),
        HumanMessage(content=text),
    ]).name


def _is_confirmed(text: str) -> bool:
    return _confirm_llm.invoke([
        SystemMessage(content="Did the user confirm yes? True for yes/confirm/ok/correct/sure, False for no/cancel/decline/wrong."),
        HumanMessage(content=text),
    ]).confirmed


# ── verify_customer ───────────────────────────────────────────────────────────

def verify_customer(state: PlumberState) -> dict:
    """Verify the customer's identity, or register them if they're new.

    The node cycles through up to three stages via the human_input interrupt loop:

    Stage 1 — Extract phone from message:
      • Found in DB  → welcome + open tickets summary → set customer_id
      • Not in DB    → store pending_phone, ask for name (or skip to Stage 3
                       if name was already in the same message)
      • No phone     → ask for phone number

    Stage 2 — Have pending_phone, waiting for name:
      • Name given   → store pending_name, show confirmation prompt
      • No name yet  → re-ask for name

    Stage 3 — Have pending_phone + pending_name, waiting for yes/no:
      • yes          → INSERT customer, set customer_id, welcome
      • no           → clear pending state, offer to try again
    """
    if state.get("customer_id") is not None:
        return {}

    messages = state["messages"]
    latest_content = (messages[-1].content
                      if hasattr(messages[-1], "content") else str(messages[-1]))

    pending_phone = state.get("pending_phone")
    pending_name  = state.get("pending_name")

    # ── Stage 3: confirmation ─────────────────────────────────────────────────
    if pending_phone and pending_name:
        if _is_confirmed(latest_content):
            conn = get_db_connection()
            cur = conn.execute(
                "INSERT INTO customers (name, phone) VALUES (?, ?)",
                (pending_name, pending_phone),
            )
            conn.commit()
            new_id = cur.lastrowid
            return {
                "customer_id": new_id,
                "pending_phone": None,
                "pending_name": None,
                "messages": [AIMessage(
                    f"Account created! Welcome, {pending_name}. "
                    f"Your account is now active. How can I help you today?"
                )],
            }
        else:
            return {
                "pending_phone": None,
                "pending_name": None,
                "messages": [AIMessage(
                    "No problem — registration cancelled. "
                    "If you'd like to try again, just share your phone number."
                )],
            }

    # ── Stage 2: have phone, waiting for name ────────────────────────────────
    if pending_phone and not pending_name:
        name = _extract_name(latest_content)
        if name:
            return {
                "pending_name": name,
                "messages": [AIMessage(
                    f"Got it! I'll create a new account for **{name}** "
                    f"with phone number **{pending_phone}**. "
                    f"Does that look right? (yes / no)"
                )],
            }
        # Name not yet provided — re-ask
        response = llm.invoke([
            SystemMessage(content=(
                "You are a PlumberBot agent registering a new customer. "
                "Their phone number was not found in our system. "
                "Ask them for their full name (first and last) to create their account. "
                "Keep it to one friendly sentence."
            )),
            *messages,
        ])
        return {"messages": [response]}

    # ── Stage 1: extract phone from message ───────────────────────────────────
    phone = _extract_phone(latest_content)

    if phone:
        rows = run_query(
            "SELECT customer_id, name FROM customers WHERE phone = ?", (phone,)
        )

        if rows:
            # ── Existing customer ─────────────────────────────────────────────
            cust = rows[0]
            ticket_summary = _open_ticket_summary(cust["customer_id"])
            welcome = (
                f"Welcome back, {cust['name']}! I've verified your account."
                + ticket_summary
                + "\n\nHow can I help you today?"
            )
            return {
                "customer_id": cust["customer_id"],
                "messages": [AIMessage(content=welcome)],
            }

        # ── Phone not in DB — start registration ──────────────────────────────
        # Optimisation: check if name is also in the same message so we can
        # skip Stage 2 and jump straight to confirmation.
        name = _extract_name(latest_content)
        if name:
            return {
                "pending_phone": phone,
                "pending_name": name,
                "messages": [AIMessage(
                    f"I couldn't find an account with **{phone}**. "
                    f"I'd like to create a new account for **{name}** "
                    f"with that number. Does that look right? (yes / no)"
                )],
            }
        return {
            "pending_phone": phone,
            "messages": [AIMessage(
                f"I couldn't find an account with **{phone}**. "
                f"Would you like to create a new account? "
                f"If so, please tell me your full name."
            )],
        }

    # ── No phone in message — ask for it ─────────────────────────────────────
    response = llm.invoke([
        SystemMessage(content=(
            "You are a PlumberBot agent. Your only job right now is account verification. "
            "Ask the customer for the phone number on their account in one short sentence. "
            "If they have no account, let them know they can create one by providing their "
            "name and phone number. Do NOT address their actual request yet."
        )),
        *messages,
    ])
    return {"messages": [response]}


# ── human_input ───────────────────────────────────────────────────────────────

def human_input(state: PlumberState) -> dict:
    """No-op interrupt node — pauses the graph and waits for user input."""
    user_input = interrupt("Waiting for customer input.")
    return {"messages": [HumanMessage(content=user_input)]}


def should_interrupt(state: PlumberState) -> str:
    return "continue" if state.get("customer_id") is not None else "interrupt"


# ── load_memory ───────────────────────────────────────────────────────────────

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


# ── save_memory ───────────────────────────────────────────────────────────────

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
