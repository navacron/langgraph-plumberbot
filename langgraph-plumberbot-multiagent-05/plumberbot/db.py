import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_HERE, "..", "db", "plumberbot.db")
BUSINESS_DB = os.getenv("BUSINESS_DB_PATH", _DEFAULT_DB)

_conn: sqlite3.Connection | None = None


def get_db_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(BUSINESS_DB, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def run_query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def run_write(sql: str, params: tuple = ()) -> int:
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid or 0
