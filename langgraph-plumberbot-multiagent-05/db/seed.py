"""Recreate and seed the PlumberBot business database.

Run from the project root:
    python db/seed.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plumberbot.db")


def seed() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE customers (
        customer_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL,
        phone        TEXT UNIQUE NOT NULL,
        email        TEXT,
        address      TEXT,
        created_at   TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE service_catalog (
        service_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT NOT NULL,
        description      TEXT,
        base_price_usd   REAL,
        typical_hours    REAL
    );

    CREATE TABLE plumbers (
        plumber_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL,
        phone        TEXT,
        specialties  TEXT,
        is_on_call   INTEGER DEFAULT 0
    );

    CREATE TABLE appointments (
        appointment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id     INTEGER REFERENCES customers(customer_id),
        plumber_id      INTEGER REFERENCES plumbers(plumber_id),
        service_id      INTEGER REFERENCES service_catalog(service_id),
        scheduled_at    TEXT,
        status          TEXT DEFAULT 'scheduled',
        notes           TEXT
    );

    CREATE TABLE tickets (
        ticket_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id  INTEGER REFERENCES customers(customer_id),
        description  TEXT NOT NULL,
        priority     TEXT DEFAULT 'medium',
        status       TEXT DEFAULT 'open',
        created_at   TEXT DEFAULT (datetime('now')),
        resolved_at  TEXT
    );

    CREATE TABLE customer_profile (
        customer_id     INTEGER PRIMARY KEY REFERENCES customers(customer_id),
        preferences     TEXT,
        service_history TEXT,
        last_updated    TEXT DEFAULT (datetime('now'))
    );
    """)

    # ── customers ───────────────────────────────────────────────────────────
    conn.executemany(
        "INSERT INTO customers (name, phone, email, address) VALUES (?,?,?,?)",
        [
            ("Jane Doe",      "(555) 111-2222", "jane.doe@email.com",  "15 Elm Street, Springfield"),
            ("Bob Smith",     "(555) 333-4444", "bob.smith@email.com", "22 Oak Street, Springfield"),
            ("Maria Garcia",  "(555) 555-6666", "maria.g@email.com",   "7 Maple Ave, Springfield"),
            ("David Lee",     "(555) 777-8888", "d.lee@email.com",     "100 Pine Blvd, Springfield"),
            ("Sarah Wilson",  "(555) 999-0000", "s.wilson@email.com",  "33 Cedar Lane, Springfield"),
            ("Tom Brown",     "(555) 123-7890", "t.brown@email.com",   "5 Birch Road, Springfield"),
        ],
    )

    # ── service_catalog ─────────────────────────────────────────────────────
    conn.executemany(
        "INSERT INTO service_catalog (name, description, base_price_usd, typical_hours) VALUES (?,?,?,?)",
        [
            ("Drain Cleaning",          "Snake or hydro-jet clogged drains",             150.00, 1.0),
            ("Leak Repair - Minor",     "Fix dripping faucets or small pipe leaks",      120.00, 1.0),
            ("Leak Repair - Major",     "Fix significant pipe leaks or bursts",          450.00, 3.0),
            ("Water Heater Inspection", "Diagnose and assess water heater issues",        95.00, 1.0),
            ("Water Heater Repair",     "Replace elements, valves, or thermostats",      250.00, 2.0),
            ("Water Heater Install",    "Supply and install new water heater",           800.00, 4.0),
            ("Toilet Repair",           "Fix running toilets, weak flush, or clogs",     130.00, 1.5),
            ("Toilet Install",          "Supply and install new toilet",                 400.00, 2.5),
            ("Emergency Burst Pipe",    "24/7 emergency burst-pipe repair",              450.00, 2.0),
            ("Sewer Inspection",        "Camera inspection of sewer line",               200.00, 1.5),
        ],
    )

    # ── plumbers ────────────────────────────────────────────────────────────
    conn.executemany(
        "INSERT INTO plumbers (name, phone, specialties, is_on_call) VALUES (?,?,?,?)",
        [
            ("Mike Torres",  "(555) 200-0001", "drain cleaning, general plumbing, emergency", 1),
            ("Sarah Kim",    "(555) 200-0002", "water heater, installation, inspection",       0),
            ("Dave Johnson", "(555) 200-0003", "emergency, burst pipe, leak repair",           0),
            ("Lisa Chen",    "(555) 200-0004", "general plumbing, toilet, drain cleaning",     0),
        ],
    )

    # ── appointments ────────────────────────────────────────────────────────
    # (customer_id, plumber_id, service_id, scheduled_at, status, notes)
    conn.executemany(
        """INSERT INTO appointments
           (customer_id, plumber_id, service_id, scheduled_at, status, notes)
           VALUES (?,?,?,?,?,?)""",
        [
            (1, 1, 1, "2026-06-15 09:00", "completed", "Main bathroom drain cleared"),
            (1, 3, 9, "2026-05-01 08:00", "completed", "Emergency — kitchen pipe burst"),
            (2, 2, 5, "2026-07-10 14:00", "scheduled", "Water heater making loud noises"),
            (3, 4, 7, "2026-07-05 10:00", "completed", "Running toilet in master bathroom"),
            (4, 1, 1, "2026-07-12 11:00", "scheduled", "Slow drain in two bathrooms"),
            (5, 2, 6, "2026-08-01 09:00", "scheduled", "New 50-gallon water heater install"),
        ],
    )

    # ── tickets ─────────────────────────────────────────────────────────────
    conn.executemany(
        """INSERT INTO tickets
           (customer_id, description, priority, status, created_at, resolved_at)
           VALUES (?,?,?,?,?,?)""",
        [
            (1, "Kitchen pipe burst — emergency repair needed",            "emergency", "resolved", "2026-05-01", "2026-05-01"),
            (2, "Water heater making loud popping; no hot water mornings",  "medium",    "open",     "2026-06-20", None),
            (3, "Toilet running constantly, wasting water",                 "low",       "resolved", "2026-07-04", "2026-07-05"),
            (4, "Two bathroom drains very slow with gurgling sounds",       "medium",    "open",     "2026-07-01", None),
            (1, "Small drip under kitchen sink after emergency repair",     "low",       "open",     "2026-05-10", None),
        ],
    )

    # ── customer_profile ────────────────────────────────────────────────────
    conn.executemany(
        """INSERT INTO customer_profile (customer_id, preferences, service_history)
           VALUES (?,?,?)""",
        [
            (1,
             "Prefers morning appointments (8am–12pm). Has a dog — please ring doorbell.",
             "Emergency burst-pipe repair May 2026. Regular drain cleaning customer."),
            (2,
             "Prefers afternoon slots. Call 30 minutes before arriving.",
             "Ongoing water heater issue since June 2026. Scheduled for repair July 2026."),
            (3,
             "Available weekdays, no strong time preference.",
             "Toilet repair July 2026. Generally satisfied with PlumberBot service."),
        ],
    )

    conn.commit()
    conn.close()

    print(f"✓ Database seeded: {DB_PATH}")
    print("  Tables: customers(6), service_catalog(10), plumbers(4), "
          "appointments(6), tickets(5), customer_profile(3)")


if __name__ == "__main__":
    seed()
