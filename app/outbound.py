"""Outbound calling: reminders, follow-ups, re-engagement.

Lives in the app package (rather than the CLI script) so both the command line
and the scheduled task endpoints can drive it.
"""

import datetime
import json
import urllib.error
import urllib.request

from app import config, database

VAPI_CALL_ENDPOINT = "https://api.vapi.ai/call"

DEFAULT_OUTBOUND_GREETING = (
    "Hello, this is Riley calling from Wellness Partners. Do you have a quick moment?"
)
REMINDER_GREETING = (
    "Hello, this is Riley calling from Wellness Partners about your upcoming "
    "appointment. Is now a good time?"
)
FOLLOWUP_GREETING = (
    "Hello, this is Riley calling from Wellness Partners to follow up on your "
    "recent enquiry. Is now a good time?"
)


def place_call(phone_number: str, context: str,
               first_message: str | None = None,
               metadata: dict | None = None) -> dict:
    """Ask Vapi to dial a number with the assistant, passing call context.

    `context` fills {{call_context}} in the system prompt so the agent knows it
    is the one calling (and why). `metadata` comes back on the end-of-call
    report, which is how outbound results get linked to their follow-up record.
    """
    api_key = config.vapi_api_key()
    assistant_id = config.vapi_assistant_id()
    phone_number_id = config.vapi_phone_number_id()

    missing = [name for name, value in [
        ("VAPI_API_KEY", api_key),
        ("VAPI_ASSISTANT_ID", assistant_id),
        ("VAPI_PHONE_NUMBER_ID", phone_number_id),
    ] if not value]
    if missing:
        print(f"[outbound skipped] Missing config: {', '.join(missing)}")
        return {"ok": False, "reason": "not configured"}

    payload = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": {"number": phone_number},
        "assistantOverrides": {
            "variableValues": {"call_context": context},
            # Without this the agent would open with the inbound greeting
            # ("Thank you for calling...") on a call it placed itself.
            "firstMessage": first_message or DEFAULT_OUTBOUND_GREETING,
        },
        "metadata": metadata or {},
    }

    req = urllib.request.Request(
        VAPI_CALL_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        print(f"[calling] {phone_number} — {context[:80]}")
        return {"ok": True, "call": body}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")[:200]
        print(f"[outbound failed] {phone_number}: HTTP {exc.code} {detail}")
        return {"ok": False, "reason": f"http {exc.code}"}
    except Exception as exc:
        print(f"[outbound failed] {phone_number}: {exc}")
        return {"ok": False, "reason": str(exc)}


def appointment_reminders(days_ahead: int = 1) -> dict:
    """Call everyone with an appointment `days_ahead` days from now."""
    target = (datetime.datetime.now(config.timezone())
              + datetime.timedelta(days=days_ahead)).date().isoformat()

    conn = database.get_connection()
    rows = conn.execute(
        "SELECT * FROM appointments WHERE status = 'booked' AND start_time LIKE ?",
        (f"{target}%",),
    ).fetchall()
    conn.close()

    placed = 0
    for row in rows:
        context = (f"Reminder call for {row['patient_name']}: {row['appointment_type']} "
                   f"appointment on {row['start_time']}. Confirm they can still attend, "
                   "and offer to reschedule if not.")
        result = place_call(
            row["callback_number"], context,
            first_message=REMINDER_GREETING,
            metadata={"workflow": "reminder", "appointment_id": row["id"]},
        )
        if result["ok"]:
            placed += 1

    return {"date": target, "found": len(rows), "calls_placed": placed}


def work_followup_queue() -> dict:
    """Call everyone in the pending follow-up queue.

    Calls are marked 'calling' here, not 'completed' — the end-of-call webhook
    records the actual outcome once the conversation finishes.
    """
    pending = database.pending_followups()

    placed = 0
    for followup in pending:
        context = (f"Follow-up call for {followup['contact_name']}: {followup['purpose']}. "
                   "Find out where they stand, answer any questions, and book them in "
                   "if they are ready.")
        result = place_call(
            followup["phone_number"], context,
            first_message=FOLLOWUP_GREETING,
            metadata={"workflow": "followup", "followup_id": followup["id"]},
        )
        if result["ok"]:
            database.mark_followup_calling(followup["id"])
            placed += 1

    return {"pending": len(pending), "calls_placed": placed}
