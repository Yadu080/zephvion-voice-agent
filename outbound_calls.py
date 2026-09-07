"""Outbound calling workflows — appointment reminders, follow-ups, re-engagement.

Usage:
    python3 outbound_calls.py reminders      # call tomorrow's appointments
    python3 outbound_calls.py followups      # work the pending follow-up queue
    python3 outbound_calls.py call +9198... "reason for the call"

Requires VAPI_API_KEY, VAPI_ASSISTANT_ID and VAPI_PHONE_NUMBER_ID in .env.
"""

import datetime
import json
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from app import config, database  # noqa: E402  (must load env first)

VAPI_CALL_ENDPOINT = "https://api.vapi.ai/call"


def place_call(phone_number: str, context: str) -> dict:
    """Ask Vapi to dial a number with the assistant, passing call context."""
    api_key = config.vapi_api_key()
    assistant_id = config.vapi_assistant_id()
    phone_number_id = config.vapi_phone_number_id()

    missing = [name for name, value in [
        ("VAPI_API_KEY", api_key),
        ("VAPI_ASSISTANT_ID", assistant_id),
        ("VAPI_PHONE_NUMBER_ID", phone_number_id),
    ] if not value]
    if missing:
        print(f"[skipped] Missing config: {', '.join(missing)}")
        return {"ok": False, "reason": "not configured"}

    payload = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": {"number": phone_number},
        "assistantOverrides": {
            "variableValues": {"call_context": context},
        },
    }

    req = urllib.request.Request(
        VAPI_CALL_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        print(f"[calling] {phone_number} — {context}")
        return {"ok": True, "call": body}
    except urllib.error.HTTPError as exc:
        print(f"[failed] {phone_number}: HTTP {exc.code} {exc.read().decode('utf-8')[:200]}")
        return {"ok": False, "reason": f"http {exc.code}"}
    except Exception as exc:
        print(f"[failed] {phone_number}: {exc}")
        return {"ok": False, "reason": str(exc)}


def appointment_reminders(days_ahead: int = 1) -> None:
    """Call everyone with an appointment `days_ahead` days from now."""
    target = (datetime.datetime.now(config.timezone())
              + datetime.timedelta(days=days_ahead)).date().isoformat()

    conn = database.get_connection()
    rows = conn.execute(
        "SELECT * FROM appointments WHERE status = 'booked' AND start_time LIKE ?",
        (f"{target}%",),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No appointments found for {target}.")
        return

    for row in rows:
        context = (f"Reminder call for {row['patient_name']}: {row['appointment_type']} "
                   f"appointment on {row['start_time']}. Confirm they can still attend, "
                   "and offer to reschedule if not.")
        place_call(row["callback_number"], context)


def work_followup_queue() -> None:
    """Call everyone in the pending follow-up queue."""
    pending = database.pending_followups()
    if not pending:
        print("No pending follow-ups.")
        return

    for followup in pending:
        context = f"Follow-up call for {followup['contact_name']}: {followup['purpose']}"
        result = place_call(followup["phone_number"], context)
        if result["ok"]:
            database.complete_followup(followup["id"], "call placed")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    if command == "reminders":
        appointment_reminders()
    elif command == "followups":
        work_followup_queue()
    elif command == "call" and len(sys.argv) >= 4:
        place_call(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
