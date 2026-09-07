"""Readable view of everything the voice agent has captured. Run with:
    python3 view_data.py
"""

from dotenv import load_dotenv

load_dotenv()

from app.database import get_connection, init_db  # noqa: E402

COL_WIDTH = 20


def _print_table(title, rows, columns):
    print(f"\n{title}")
    print("=" * len(title))

    if not rows:
        print("(no records yet)")
        return

    header = " | ".join(col.ljust(COL_WIDTH) for col in columns)
    print(header)
    print("-" * len(header))

    for row in rows:
        keys = row.keys()
        cells = []
        for col in columns:
            value = row[col] if col in keys else ""
            cells.append(str(value if value is not None else "")[:COL_WIDTH].ljust(COL_WIDTH))
        print(" | ".join(cells))


def main():
    init_db()
    conn = get_connection()

    _print_table(
        "APPOINTMENTS",
        conn.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall(),
        ["id", "patient_name", "appointment_type", "start_time", "status"],
    )

    _print_table(
        "LEADS / ENQUIRIES",
        conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall(),
        ["id", "caller_name", "callback_number", "category", "qualification", "reason"],
    )

    _print_table(
        "SUPPORT TICKETS",
        conn.execute("SELECT * FROM support_tickets ORDER BY created_at DESC").fetchall(),
        ["id", "caller_name", "issue", "priority", "status"],
    )

    _print_table(
        "CALL SUMMARIES",
        conn.execute("SELECT * FROM call_summaries ORDER BY created_at DESC").fetchall(),
        ["id", "call_id", "caller_number", "ended_reason", "summary"],
    )

    _print_table(
        "FOLLOW-UP QUEUE",
        conn.execute("SELECT * FROM followups ORDER BY created_at DESC").fetchall(),
        ["id", "contact_name", "phone_number", "purpose", "status"],
    )

    conn.close()
    print()


if __name__ == "__main__":
    main()
