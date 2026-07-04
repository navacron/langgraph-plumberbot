"""Dispatch tools — manage service tickets and emergency response.

customer_id is injected automatically from graph state via InjectedState.
"""

from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..db import get_db_connection, run_query


@tool
def get_open_tickets(
    customer_id: Annotated[int, InjectedState("customer_id")]
) -> list[dict]:
    """Get all open service tickets for the verified customer."""
    return run_query(
        "SELECT * FROM tickets WHERE customer_id = ? AND status = 'open' ORDER BY created_at DESC",
        (customer_id,),
    )


@tool
def get_all_tickets(
    customer_id: Annotated[int, InjectedState("customer_id")]
) -> list[dict]:
    """Get all tickets (open and resolved) for the verified customer."""
    return run_query(
        "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC",
        (customer_id,),
    )


@tool
def create_ticket(
    customer_id: Annotated[int, InjectedState("customer_id")],
    description: str,
    priority: Literal["low", "medium", "high", "emergency"] = "medium",
) -> dict:
    """Create a new service ticket for the verified customer.

    Args:
        description: Full description of the plumbing issue
        priority: 'low', 'medium', 'high', or 'emergency'
    """
    conn = get_db_connection()
    cur = conn.execute(
        "INSERT INTO tickets (customer_id, description, priority, status) VALUES (?, ?, ?, 'open')",
        (customer_id, description, priority),
    )
    conn.commit()
    return {
        "ticket_id": cur.lastrowid,
        "status": "open",
        "priority": priority,
        "message": f"Ticket #{cur.lastrowid} created with {priority} priority.",
    }


@tool
def get_plumber_on_call() -> dict:
    """Get the plumber currently on call for emergency dispatch."""
    rows = run_query(
        "SELECT plumber_id, name, phone, specialties FROM plumbers WHERE is_on_call = 1 LIMIT 1"
    )
    return rows[0] if rows else {"error": "No plumber currently on call — please call (555) 123-4567"}


dispatch_tools = [get_open_tickets, get_all_tickets, create_ticket, get_plumber_on_call]
