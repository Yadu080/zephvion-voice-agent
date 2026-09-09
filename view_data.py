"""Readable view of everything the voice agent has captured. Run with:
    python3 view_data.py
"""

from dotenv import load_dotenv

load_dotenv()

from app import database  # noqa: E402

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
        cells = []
        for col in columns:
            value = row.get(col, "")
            cells.append(str(value if value is not None else "")[:COL_WIDTH].ljust(COL_WIDTH))
        print(" | ".join(cells))


def main():
    database.init_db()
    print(f"(storage: {database.backend_name()})")

    _print_table(
        "APPOINTMENTS",
        database.fetch_all("appointments"),
        ["id", "patient_name", "appointment_type", "start_time", "status"],
    )

    _print_table(
        "LEADS / ENQUIRIES",
        database.fetch_all("leads"),
        ["id", "caller_name", "callback_number", "category", "qualification", "reason"],
    )

    _print_table(
        "SUPPORT TICKETS",
        database.fetch_all("support_tickets"),
        ["id", "caller_name", "issue", "priority", "status"],
    )

    _print_table(
        "CALL SUMMARIES",
        database.fetch_all("call_summaries"),
        ["id", "call_id", "caller_number", "ended_reason", "summary"],
    )

    _print_table(
        "FOLLOW-UP QUEUE",
        database.fetch_all("followups"),
        ["id", "contact_name", "phone_number", "purpose", "status"],
    )

    print()


if __name__ == "__main__":
    main()
