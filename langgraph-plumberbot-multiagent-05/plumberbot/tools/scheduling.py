"""Scheduling tools — query the business DB for appointments and services.

customer_id is injected automatically from graph state via InjectedState.
The LLM never sees customer_id in its tool schema.
"""

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..db import get_db_connection, run_query


@tool
def get_customer_info(
    customer_id: Annotated[int, InjectedState("customer_id")]
) -> dict:
    """Get the verified customer's name, phone, email, and address."""
    rows = run_query(
        "SELECT customer_id, name, phone, email, address FROM customers WHERE customer_id = ?",
        (customer_id,),
    )
    return rows[0] if rows else {"error": "Customer not found"}


@tool
def get_service_catalog() -> list[dict]:
    """List all available plumbing services with descriptions and base pricing."""
    return run_query(
        "SELECT name, description, base_price_usd, typical_hours FROM service_catalog ORDER BY name"
    )


@tool
def get_appointments(
    customer_id: Annotated[int, InjectedState("customer_id")]
) -> list[dict]:
    """Get all appointments for the verified customer, most recent first."""
    return run_query(
        """
        SELECT a.appointment_id, a.scheduled_at, a.status, a.notes,
               p.name AS plumber_name, s.name AS service_name, s.base_price_usd
        FROM appointments a
        JOIN plumbers p ON a.plumber_id = p.plumber_id
        JOIN service_catalog s ON a.service_id = s.service_id
        WHERE a.customer_id = ?
        ORDER BY a.scheduled_at DESC
        """,
        (customer_id,),
    )


@tool
def get_available_plumbers(service_type: str = "") -> list[dict]:
    """Find plumbers. Filter by service_type keyword (e.g. 'drain', 'water heater', 'emergency').
    Pass empty string to list all plumbers."""
    if service_type:
        return run_query(
            "SELECT plumber_id, name, phone, specialties, is_on_call FROM plumbers WHERE specialties LIKE ?",
            (f"%{service_type}%",),
        )
    return run_query("SELECT plumber_id, name, phone, specialties, is_on_call FROM plumbers")


@tool
def book_appointment(
    customer_id: Annotated[int, InjectedState("customer_id")],
    plumber_id: int,
    service_id: int,
    scheduled_at: str,
    notes: str = "",
) -> dict:
    """Book a new appointment.

    Args:
        plumber_id: ID from get_available_plumbers
        service_id: ID from get_service_catalog (use SELECT service_id to get numeric ID)
        scheduled_at: ISO datetime string, e.g. '2026-08-15 10:00'
        notes: Optional notes about the job
    """
    conn = get_db_connection()
    cur = conn.execute(
        """INSERT INTO appointments
           (customer_id, plumber_id, service_id, scheduled_at, status, notes)
           VALUES (?, ?, ?, ?, 'scheduled', ?)""",
        (customer_id, plumber_id, service_id, scheduled_at, notes),
    )
    conn.commit()
    return {
        "appointment_id": cur.lastrowid,
        "status": "scheduled",
        "scheduled_at": scheduled_at,
        "message": "Appointment booked successfully.",
    }


scheduling_tools = [
    get_customer_info,
    get_service_catalog,
    get_appointments,
    get_available_plumbers,
    book_appointment,
]
