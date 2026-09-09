"""Storage layer.

Uses Postgres when DATABASE_URL is set, and SQLite otherwise. Hosts with an
ephemeral filesystem (Render's free tier included) wipe a local SQLite file on
every redeploy, so a free hosted Postgres is what makes the records durable —
while SQLite keeps local development dependency-free.
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"


def database_url():
    return os.environ.get("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    return bool(database_url())


def backend_name() -> str:
    return "postgres" if using_postgres() else "sqlite"


def _connect():
    if using_postgres():
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(database_url(), row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_connection():
    return _connect()


def _sql(query: str) -> str:
    """Queries are written with '?' placeholders; Postgres wants '%s'."""
    return query.replace("?", "%s") if using_postgres() else query


def _rows(cursor_or_conn, query, params=()):
    conn = cursor_or_conn
    cur = conn.execute(_sql(query), params)
    return [dict(r) for r in cur.fetchall()]


def _one(conn, query, params=()):
    rows = _rows(conn, query, params)
    return rows[0] if rows else None


def _insert(query, params):
    """Insert and return the new row's id, on either backend."""
    conn = _connect()
    try:
        if using_postgres():
            cur = conn.execute(_sql(query) + " RETURNING id", params)
            new_id = cur.fetchone()["id"]
        else:
            cur = conn.execute(query, params)
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def _execute(query, params=()):
    conn = _connect()
    try:
        conn.execute(_sql(query), params)
        conn.commit()
    finally:
        conn.close()


# --- Schema ----------------------------------------------------------------

def _pk() -> str:
    return "SERIAL PRIMARY KEY" if using_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _timestamp() -> str:
    return ("TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if using_postgres()
            else "TEXT DEFAULT CURRENT_TIMESTAMP")


SCHEMA = {
    "leads": """
        id {pk},
        caller_name TEXT,
        callback_number TEXT,
        category TEXT,
        reason TEXT,
        notes TEXT,
        email TEXT,
        qualification TEXT,
        qualification_score INTEGER,
        created_at {ts}
    """,
    "appointments": """
        id {pk},
        patient_name TEXT,
        callback_number TEXT,
        appointment_type TEXT,
        start_time TEXT,
        end_time TEXT,
        calendar_event_id TEXT,
        email TEXT,
        status TEXT DEFAULT 'booked',
        created_at {ts}
    """,
    "support_tickets": """
        id {pk},
        caller_name TEXT,
        callback_number TEXT,
        issue TEXT,
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'open',
        created_at {ts}
    """,
    "call_summaries": """
        id {pk},
        call_id TEXT,
        caller_number TEXT,
        summary TEXT,
        transcript TEXT,
        ended_reason TEXT,
        duration_seconds REAL,
        created_at {ts}
    """,
    "followups": """
        id {pk},
        contact_name TEXT,
        phone_number TEXT,
        purpose TEXT,
        status TEXT DEFAULT 'pending',
        outcome TEXT,
        created_at {ts},
        completed_at TEXT
    """,
}

# Columns added after the original schema shipped, applied to existing databases.
MIGRATIONS = [
    ("leads", "email", "TEXT"),
    ("leads", "qualification", "TEXT"),
    ("leads", "qualification_score", "INTEGER"),
    ("appointments", "email", "TEXT"),
]


def _existing_columns(conn, table):
    if using_postgres():
        rows = _rows(conn,
                     "SELECT column_name AS name FROM information_schema.columns "
                     "WHERE table_name = ?", (table,))
    else:
        rows = [dict(r) for r in conn.execute(f"PRAGMA table_info({table})")]
    return {r["name"] for r in rows}


def init_db():
    conn = _connect()
    try:
        for table, body in SCHEMA.items():
            columns = body.format(pk=_pk(), ts=_timestamp())
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")

        for table, column, col_type in MIGRATIONS:
            if column not in _existing_columns(conn, table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

        conn.commit()
    finally:
        conn.close()


# --- Leads -----------------------------------------------------------------

def insert_lead(caller_name, callback_number, category, reason, notes,
                email=None, qualification=None, qualification_score=None):
    return _insert(
        "INSERT INTO leads (caller_name, callback_number, category, reason, notes, "
        "email, qualification, qualification_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (caller_name, callback_number, category, reason, notes,
         email, qualification, qualification_score),
    )


# --- Appointments ----------------------------------------------------------

def insert_appointment(patient_name, callback_number, appointment_type,
                       start_time, end_time, calendar_event_id, email=None):
    return _insert(
        "INSERT INTO appointments (patient_name, callback_number, appointment_type, "
        "start_time, end_time, calendar_event_id, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (patient_name, callback_number, appointment_type, start_time, end_time,
         calendar_event_id, email),
    )


def _digits(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())[-10:]


def find_latest_booked_appointment(patient_name, callback_number):
    """Find a caller's active appointment, tolerating phone-format differences."""
    conn = _connect()
    try:
        rows = _rows(conn, "SELECT * FROM appointments WHERE status = 'booked' "
                           "ORDER BY start_time DESC")
    finally:
        conn.close()

    digits = _digits(callback_number)
    name = (patient_name or "").strip().lower()

    # Prefer an exact match on both name and number, then fall back to either,
    # since callers often give the number in a different format than at booking.
    for require_both in (True, False):
        for row in rows:
            row_name = (row.get("patient_name") or "").strip().lower()
            name_match = bool(row_name) and row_name == name
            phone_match = bool(digits) and _digits(row.get("callback_number")) == digits
            if require_both and name_match and phone_match:
                return row
            if not require_both and (name_match or phone_match):
                return row
    return None


def update_appointment_time(appointment_id, start_time, end_time):
    _execute("UPDATE appointments SET start_time = ?, end_time = ? WHERE id = ?",
             (start_time, end_time, appointment_id))


def mark_appointment_cancelled(appointment_id):
    _execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))


# --- Support tickets -------------------------------------------------------

def insert_support_ticket(caller_name, callback_number, issue, priority="normal"):
    return _insert(
        "INSERT INTO support_tickets (caller_name, callback_number, issue, priority) "
        "VALUES (?, ?, ?, ?)",
        (caller_name, callback_number, issue, priority),
    )


# --- Call summaries --------------------------------------------------------

def insert_call_summary(call_id, caller_number, summary, transcript,
                        ended_reason=None, duration_seconds=None):
    return _insert(
        "INSERT INTO call_summaries (call_id, caller_number, summary, transcript, "
        "ended_reason, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (call_id, caller_number, summary, transcript, ended_reason, duration_seconds),
    )


# --- Follow-ups (outbound) -------------------------------------------------

def insert_followup(contact_name, phone_number, purpose):
    return _insert(
        "INSERT INTO followups (contact_name, phone_number, purpose) VALUES (?, ?, ?)",
        (contact_name, phone_number, purpose),
    )


def pending_followups():
    conn = _connect()
    try:
        return _rows(conn, "SELECT * FROM followups WHERE status = 'pending' "
                           "ORDER BY created_at")
    finally:
        conn.close()


def get_followup(followup_id):
    conn = _connect()
    try:
        return _one(conn, "SELECT * FROM followups WHERE id = ?", (followup_id,))
    finally:
        conn.close()


def complete_followup(followup_id, outcome):
    _execute("UPDATE followups SET status = 'completed', outcome = ?, "
             "completed_at = CURRENT_TIMESTAMP WHERE id = ?", (outcome, followup_id))


def mark_followup_calling(followup_id):
    """Call placed but not yet finished — the end-of-call report closes it out."""
    _execute("UPDATE followups SET status = 'calling' WHERE id = ?", (followup_id,))


def requeue_followup(followup_id, note):
    """Call didn't reach the person — put it back in the queue to retry."""
    _execute("UPDATE followups SET status = 'pending', outcome = ? WHERE id = ?",
             (note, followup_id))


# --- Reporting -------------------------------------------------------------

def fetch_all(table, order_by="created_at DESC"):
    conn = _connect()
    try:
        return _rows(conn, f"SELECT * FROM {table} ORDER BY {order_by}")
    finally:
        conn.close()
