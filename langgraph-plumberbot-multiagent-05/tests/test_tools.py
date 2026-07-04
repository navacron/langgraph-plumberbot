"""Test DB tool queries against the seed database.

No API key required — all tests run against the committed plumberbot.db.
"""

import os
import sys

import pytest

# Allow importing plumberbot from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point at the seed DB
os.environ.setdefault(
    "BUSINESS_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "db", "plumberbot.db"),
)

from plumberbot.db import run_query, run_write  # noqa: E402


# ── customers ──────────────────────────────────────────────────────────────────

def test_customers_seeded():
    rows = run_query("SELECT * FROM customers")
    assert len(rows) == 6, f"Expected 6 customers, got {len(rows)}"


def test_customer_lookup_by_phone():
    rows = run_query(
        "SELECT customer_id, name FROM customers WHERE phone = ?",
        ("(555) 111-2222",),
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "Jane Doe"
    assert rows[0]["customer_id"] == 1


def test_customer_phone_not_found():
    rows = run_query(
        "SELECT customer_id FROM customers WHERE phone = ?",
        ("(555) 000-0000",),
    )
    assert rows == []


# ── service_catalog ───────────────────────────────────────────────────────────

def test_service_catalog_seeded():
    rows = run_query("SELECT * FROM service_catalog")
    assert len(rows) == 10


def test_service_catalog_has_drain_cleaning():
    rows = run_query(
        "SELECT base_price_usd FROM service_catalog WHERE name = 'Drain Cleaning'"
    )
    assert len(rows) == 1
    assert rows[0]["base_price_usd"] == 150.00


# ── plumbers ──────────────────────────────────────────────────────────────────

def test_plumbers_seeded():
    rows = run_query("SELECT * FROM plumbers")
    assert len(rows) == 4


def test_on_call_plumber_exists():
    rows = run_query("SELECT name FROM plumbers WHERE is_on_call = 1")
    assert len(rows) == 1
    assert rows[0]["name"] == "Mike Torres"


def test_plumber_specialty_filter():
    rows = run_query(
        "SELECT name FROM plumbers WHERE specialties LIKE ?", ("%water heater%",)
    )
    assert len(rows) >= 1
    names = [r["name"] for r in rows]
    assert "Sarah Kim" in names


# ── appointments ──────────────────────────────────────────────────────────────

def test_appointments_seeded():
    rows = run_query("SELECT * FROM appointments")
    assert len(rows) == 6


def test_customer_appointments_join():
    rows = run_query(
        """
        SELECT a.scheduled_at, p.name AS plumber_name, s.name AS service_name
        FROM appointments a
        JOIN plumbers p ON a.plumber_id = p.plumber_id
        JOIN service_catalog s ON a.service_id = s.service_id
        WHERE a.customer_id = 1
        ORDER BY a.scheduled_at DESC
        """
    )
    assert len(rows) == 2  # Jane Doe has 2 appointments
    # Most recent first
    assert rows[0]["scheduled_at"] > rows[1]["scheduled_at"]


# ── tickets ───────────────────────────────────────────────────────────────────

def test_tickets_seeded():
    rows = run_query("SELECT * FROM tickets")
    assert len(rows) == 5


def test_open_tickets_for_customer():
    rows = run_query(
        "SELECT * FROM tickets WHERE customer_id = 1 AND status = 'open'"
    )
    assert len(rows) == 1  # Jane Doe has 1 open ticket


def test_ticket_write_and_query():
    ticket_id = run_write(
        "INSERT INTO tickets (customer_id, description, priority, status) VALUES (?,?,?,?)",
        (2, "Test ticket from pytest", "low", "open"),
    )
    assert ticket_id > 0
    rows = run_query("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
    assert len(rows) == 1
    assert rows[0]["description"] == "Test ticket from pytest"
    # Cleanup
    run_write("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))


# ── customer_profile ──────────────────────────────────────────────────────────

def test_profiles_seeded():
    rows = run_query("SELECT * FROM customer_profile")
    assert len(rows) == 3


def test_profile_lookup():
    rows = run_query(
        "SELECT preferences FROM customer_profile WHERE customer_id = 1"
    )
    assert len(rows) == 1
    assert "morning" in rows[0]["preferences"].lower()
