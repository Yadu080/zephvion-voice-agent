"""Create or update all 9 Vapi tools in one go.

Matches existing tools by function name: updates them if they already exist,
creates them if they don't — so it's safe to run more than once.

Usage:
    python3 setup_vapi_tools.py            # create/update all tools
    python3 setup_vapi_tools.py --list     # just show what's currently there

Requires VAPI_API_KEY in .env, and SERVER_URL below pointing at your deployment.
"""

import json
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from app import config  # noqa: E402

SERVER_URL = "https://zephvion-voice-agent.onrender.com/tools/webhook"
TIMEOUT_SECONDS = 20
API = "https://api.vapi.ai/tool"


def _string(desc, enum=None):
    field = {"type": "string", "description": desc}
    if enum:
        field["enum"] = enum
    return field


TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Check whether a specific appointment date and time is free before offering it "
            "to the caller. Returns alternative times if the requested slot is taken."
        ),
        "properties": {
            "date": _string("Appointment date in YYYY-MM-DD format"),
            "time": _string("Appointment time in 24-hour HH:MM format"),
            "duration_minutes": {"type": "number", "description": "Length in minutes, defaults to 30"},
        },
        "required": ["date", "time"],
    },
    {
        "name": "book_appointment",
        "description": (
            "Book a confirmed appointment on the clinic calendar. Only call this after the "
            "caller has confirmed the date and time."
        ),
        "properties": {
            "patient_name": _string("Patient's full name"),
            "callback_number": _string("Phone number to reach the patient, digits only"),
            "appointment_type": _string("Type of appointment or reason for the visit"),
            "date": _string("Appointment date in YYYY-MM-DD format"),
            "time": _string("Appointment time in 24-hour HH:MM format"),
            "email": _string("Email address for the written confirmation, if the caller gives one"),
            "duration_minutes": {"type": "number", "description": "Length in minutes, defaults to 30"},
        },
        "required": ["patient_name", "callback_number", "appointment_type", "date", "time"],
    },
    {
        "name": "reschedule_appointment",
        "description": (
            "Move an existing appointment to a new date and time. Finds the caller's current "
            "appointment from their name and callback number."
        ),
        "properties": {
            "patient_name": _string("Patient's full name"),
            "callback_number": _string("Phone number the appointment was booked under, digits only"),
            "new_date": _string("New date in YYYY-MM-DD format"),
            "new_time": _string("New time in 24-hour HH:MM format"),
            "duration_minutes": {"type": "number", "description": "Length in minutes, defaults to 30"},
        },
        "required": ["patient_name", "callback_number", "new_date", "new_time"],
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment and remove it from the clinic calendar.",
        "properties": {
            "patient_name": _string("Patient's full name"),
            "callback_number": _string("Phone number the appointment was booked under, digits only"),
        },
        "required": ["patient_name", "callback_number"],
    },
    {
        "name": "capture_lead",
        "description": (
            "Record a caller's details for follow-up. Use for general enquiries and for "
            "callers who want a human to call them back. Include the qualifying answers "
            "whenever the caller has given them."
        ),
        "properties": {
            "caller_name": _string("Caller's full name"),
            "callback_number": _string("Phone number to reach the caller, digits only"),
            "category": _string("Type of record", ["enquiry", "escalation"]),
            "reason": _string("Short reason for the call"),
            "notes": _string("Any extra context from the conversation"),
            "email": _string("Email address, if the caller gives one"),
            "timeframe": _string(
                "How soon the caller wants to proceed",
                ["immediately", "this_week", "this_month", "few_months", "just_researching"],
            ),
            "intent": _string(
                "How ready the caller is to commit",
                ["ready_to_book", "comparing_options", "wants_information", "general_enquiry"],
            ),
            "budget": _string(
                "How the caller intends to pay",
                ["insured", "self_pay_confirmed", "unsure", "no_budget"],
            ),
        },
        "required": ["caller_name", "callback_number", "category", "reason"],
    },
    {
        "name": "answer_question",
        "description": (
            "Answer a factual question about the clinic — opening hours, location and parking, "
            "insurance accepted, costs, what to bring, cancellation policy, services offered, "
            "appointment lengths, or new patient registration. Use this instead of answering "
            "from memory so the information is always correct."
        ),
        "properties": {
            "question": _string("The caller's question, in their own words"),
        },
        "required": ["question"],
    },
    {
        "name": "create_support_ticket",
        "description": (
            "Raise a support ticket when a caller reports a problem, complaint or billing issue "
            "that needs the team to investigate. Returns a ticket number to give the caller."
        ),
        "properties": {
            "caller_name": _string("Caller's full name"),
            "callback_number": _string("Phone number to reach the caller, digits only"),
            "issue": _string("Clear description of the problem the caller reported"),
            "priority": _string(
                "How urgent the issue is. Use high for billing errors, time-sensitive "
                "problems, or an upset caller.",
                ["low", "normal", "high"],
            ),
        },
        "required": ["caller_name", "callback_number", "issue"],
    },
    {
        "name": "check_business_hours",
        "description": (
            "Check whether the clinic is currently open, and when it next reopens. Use when "
            "the caller asks if you are open, or mentions calling late or early."
        ),
        "properties": {},
        "required": [],
    },
    {
        "name": "schedule_followup",
        "description": (
            "Schedule a follow-up call back to the caller for a later time, when they ask to "
            "be contacted again about something."
        ),
        "properties": {
            "contact_name": _string("Name of the person to call back"),
            "phone_number": _string("Number to call back on, digits only"),
            "purpose": _string("What the follow-up call should be about"),
        },
        "required": ["contact_name", "phone_number", "purpose"],
    },
]


def _payload(spec):
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": {
                "type": "object",
                "properties": spec["properties"],
                "required": spec["required"],
            },
        },
        "server": {"url": SERVER_URL, "timeoutSeconds": TIMEOUT_SECONDS},
    }


def _request(method, url, api_key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Cloudflare (in front of api.vapi.ai) blocks urllib's default
        # "Python-urllib/x.y" User-Agent as bot-like — send a normal one.
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def existing_tools(api_key):
    tools = _request("GET", API, api_key)
    found = {}
    for tool in tools if isinstance(tools, list) else []:
        name = (tool.get("function") or {}).get("name")
        if name:
            found[name] = tool["id"]
    return found


def main():
    api_key = config.vapi_api_key()
    if not api_key:
        print("VAPI_API_KEY is not set in .env — add it and run again.")
        print("Get it from the Vapi dashboard under API Keys.")
        return

    try:
        current = existing_tools(api_key)
    except urllib.error.HTTPError as exc:
        print(f"Could not list tools: HTTP {exc.code} {exc.read().decode('utf-8')[:200]}")
        return

    if "--list" in sys.argv:
        print(f"{len(current)} tool(s) currently on this Vapi account:")
        for name, tool_id in sorted(current.items()):
            print(f"  {name}  ({tool_id})")
        return

    for spec in TOOLS:
        name = spec["name"]
        payload = _payload(spec)
        try:
            if name in current:
                _request("PATCH", f"{API}/{current[name]}", api_key, payload)
                print(f"updated  {name}")
            else:
                _request("POST", API, api_key, payload)
                print(f"created  {name}")
        except urllib.error.HTTPError as exc:
            print(f"FAILED   {name}: HTTP {exc.code} {exc.read().decode('utf-8')[:300]}")
        except Exception as exc:
            print(f"FAILED   {name}: {exc}")

    print("\nDone. Now attach the tools to your assistant in the Vapi dashboard "
          "(Assistants → your assistant → Tools tab).")


if __name__ == "__main__":
    main()
