import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(conn, table, column, col_type):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_name TEXT,
            callback_number TEXT,
            category TEXT,
            reason TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            callback_number TEXT,
            appointment_type TEXT,
            start_time TEXT,
            end_time TEXT,
            calendar_event_id TEXT,
            status TEXT DEFAULT 'booked',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_name TEXT,
            callback_number TEXT,
            issue TEXT,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS call_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            caller_number TEXT,
            summary TEXT,
            transcript TEXT,
            ended_reason TEXT,
            duration_seconds REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_name TEXT,
            phone_number TEXT,
            purpose TEXT,
            status TEXT DEFAULT 'pending',
            outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    """)

    # Migrations for databases created by earlier versions.
    _add_column_if_missing(conn, "leads", "email", "TEXT")
    _add_column_if_missing(conn, "leads", "qualification", "TEXT")
    _add_column_if_missing(conn, "leads", "qualification_score", "INTEGER")
    _add_column_if_missing(conn, "appointments", "email", "TEXT")

    conn.commit()
    conn.close()


# --- Leads -----------------------------------------------------------------

def insert_lead(caller_name, callback_number, category, reason, notes,
                email=None, qualification=None, qualification_score=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO leads (caller_name, callback_number, category, reason, notes, "
        "email, qualification, qualification_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (caller_name, callback_number, category, reason, notes,
         email, qualification, qualification_score),
    )
    conn.commit()
    lead_id = cur.lastrowid
    conn.close()
    return lead_id


# --- Appointments ----------------------------------------------------------

def insert_appointment(patient_name, callback_number, appointment_type,
                       start_time, end_time, calendar_event_id, email=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO appointments (patient_name, callback_number, appointment_type, "
        "start_time, end_time, calendar_event_id, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (patient_name, callback_number, appointment_type, start_time, end_time,
         calendar_event_id, email),
    )
    conn.commit()
    appt_id = cur.lastrowid
    conn.close()
    return appt_id


def find_latest_booked_appointment(patient_name, callback_number):
    """Find a caller's active appointment, tolerating phone-format differences."""
    digits = _digits(callback_number)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM appointments WHERE status = 'booked' ORDER BY start_time DESC"
    ).fetchall()
    conn.close()

    name = (patient_name or "").strip().lower()

    # Prefer an exact match on both name and number, then fall back to either,
    # since callers often give the number in a different format than at booking.
    for require_both in (True, False):
        for row in rows:
            row_name = (row["patient_name"] or "").strip().lower()
            name_match = bool(row_name) and row_name == name
            phone_match = bool(digits) and _digits(row["callback_number"]) == digits
            if require_both and name_match and phone_match:
                return dict(row)
            if not require_both and (name_match or phone_match):
                return dict(row)
    return None


def _digits(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())[-10:]


def update_appointment_time(appointment_id, start_time, end_time):
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET start_time = ?, end_time = ? WHERE id = ?",
        (start_time, end_time, appointment_id),
    )
    conn.commit()
    conn.close()


def mark_appointment_cancelled(appointment_id):
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,)
    )
    conn.commit()
    conn.close()


# --- Support tickets -------------------------------------------------------

def insert_support_ticket(caller_name, callback_number, issue, priority="normal"):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO support_tickets (caller_name, callback_number, issue, priority) "
        "VALUES (?, ?, ?, ?)",
        (caller_name, callback_number, issue, priority),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()
    return ticket_id


# --- Call summaries --------------------------------------------------------

def insert_call_summary(call_id, caller_number, summary, transcript,
                        ended_reason=None, duration_seconds=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO call_summaries (call_id, caller_number, summary, transcript, "
        "ended_reason, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (call_id, caller_number, summary, transcript, ended_reason, duration_seconds),
    )
    conn.commit()
    summary_id = cur.lastrowid
    conn.close()
    return summary_id


# --- Follow-ups (outbound) -------------------------------------------------

def insert_followup(contact_name, phone_number, purpose):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO followups (contact_name, phone_number, purpose) VALUES (?, ?, ?)",
        (contact_name, phone_number, purpose),
    )
    conn.commit()
    followup_id = cur.lastrowid
    conn.close()
    return followup_id


def pending_followups():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM followups WHERE status = 'pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_followup(followup_id, outcome):
    conn = get_connection()
    conn.execute(
        "UPDATE followups SET status = 'completed', outcome = ?, "
        "completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (outcome, followup_id),
    )
    conn.commit()
    conn.close()


def mark_followup_calling(followup_id):
    """Call placed but not yet finished — the end-of-call report closes it out."""
    conn = get_connection()
    conn.execute("UPDATE followups SET status = 'calling' WHERE id = ?", (followup_id,))
    conn.commit()
    conn.close()


def requeue_followup(followup_id, note):
    """Call didn't reach the person — put it back in the queue to retry."""
    conn = get_connection()
    conn.execute(
        "UPDATE followups SET status = 'pending', outcome = ? WHERE id = ?",
        (note, followup_id),
    )
    conn.commit()
    conn.close()


def get_followup(followup_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM followups WHERE id = ?", (followup_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
