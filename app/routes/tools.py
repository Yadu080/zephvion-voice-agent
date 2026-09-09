import datetime
import json

from fastapi import APIRouter, Request

from app import (business_hours, calendar_service, config, database,
                 knowledge_base, notifications, qualification)

router = APIRouter()


@router.post("/tools/webhook")
async def tools_webhook(request: Request):
    body = await request.json()
    tool_calls = body["message"]["toolCallList"]
    results = []

    for call in tool_calls:
        call_id, name, args = _extract_call(call)

        try:
            result = _dispatch(name, args)
        except Exception as exc:
            print(f"[tool {name} failed] {exc}")
            result = f"Sorry, something went wrong: {exc}"

        results.append({"toolCallId": call_id, "result": result})

    return {"results": results}


def _extract_call(call: dict):
    """Vapi's tool-call shape varies (top-level name/arguments vs nested
    under 'function', arguments as dict vs JSON string) — handle all of it."""
    call_id = call.get("id")

    if "name" in call:
        name = call["name"]
        raw_args = call.get("arguments", {})
    else:
        func = call.get("function", {})
        name = func.get("name")
        raw_args = func.get("arguments", func.get("parameters", {}))

    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = raw_args or {}

    return call_id, name, args


def _dispatch(name: str, args: dict) -> str:
    handlers = {
        "check_availability": _check_availability,
        "book_appointment": _book_appointment,
        "reschedule_appointment": _reschedule_appointment,
        "cancel_appointment": _cancel_appointment,
        "capture_lead": _capture_lead,
        "answer_question": _answer_question,
        "create_support_ticket": _create_support_ticket,
        "check_business_hours": _check_business_hours,
        "schedule_followup": _schedule_followup,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    return handler(args)


def _duration(args):
    return int(args.get("duration_minutes") or config.DEFAULT_APPOINTMENT_MINUTES)


def _reject_past_date(date_str: str, time_str: str) -> str | None:
    """Guard against the model inventing a year and booking in the past.

    Returns an error message for the agent to relay, or None if the date is fine.
    """
    try:
        when = datetime.datetime.fromisoformat(f"{date_str}T{time_str}").replace(
            tzinfo=config.timezone()
        )
    except ValueError:
        return (f"'{date_str} {time_str}' isn't a valid date and time. Please ask the "
                "caller to confirm the date, then use YYYY-MM-DD and 24-hour HH:MM.")

    now = datetime.datetime.now(config.timezone())
    if when < now:
        return (f"{date_str} at {time_str} is in the past — today is "
                f"{now.strftime('%A %d %B %Y')}. Ask the caller to confirm the date "
                "they meant, and book it in the future.")
    return None


# --- Appointments ----------------------------------------------------------

def _check_availability(args: dict) -> str:
    problem = _reject_past_date(args["date"], args["time"])
    if problem:
        return problem

    res = calendar_service.check_availability(
        date_str=args["date"],
        time_str=args["time"],
        duration_minutes=_duration(args),
    )
    if res["available"]:
        return "That slot is available."
    if res["alternatives"]:
        return f"That slot is not available. Alternative times that day: {', '.join(res['alternatives'])}."
    return "That slot is not available and there are no other openings that day."


def _book_appointment(args: dict) -> str:
    problem = _reject_past_date(args["date"], args["time"])
    if problem:
        return problem

    booking = calendar_service.book_appointment(
        patient_name=args["patient_name"],
        callback_number=args["callback_number"],
        appointment_type=args["appointment_type"],
        date_str=args["date"],
        time_str=args["time"],
        duration_minutes=_duration(args),
    )
    database.insert_appointment(
        patient_name=args["patient_name"],
        callback_number=args["callback_number"],
        appointment_type=args["appointment_type"],
        start_time=booking["start"],
        end_time=booking["end"],
        calendar_event_id=booking["event_id"],
        email=args.get("email"),
    )
    notifications.appointment_booked({
        "patient_name": args["patient_name"],
        "callback_number": args["callback_number"],
        "appointment_type": args["appointment_type"],
        "date": args["date"],
        "time": args["time"],
        "email": args.get("email"),
    })

    confirmation = "A confirmation email is on its way." if args.get("email") else ""
    return (f"Appointment booked for {args['patient_name']} on {args['date']} "
            f"at {args['time']}. {confirmation}").strip()


def _reschedule_appointment(args: dict) -> str:
    patient_name = args["patient_name"]
    callback_number = args["callback_number"]

    existing = database.find_latest_booked_appointment(patient_name, callback_number)
    if not existing:
        return (f"I couldn't find an existing appointment for {patient_name} with that "
                "callback number. Could you double check the name and number?")

    problem = _reject_past_date(args["new_date"], args["new_time"])
    if problem:
        return problem

    duration_minutes = _duration(args)
    availability = calendar_service.check_availability(
        date_str=args["new_date"], time_str=args["new_time"],
        duration_minutes=duration_minutes,
    )
    if not availability["available"]:
        if availability["alternatives"]:
            return ("That new time isn't available. Alternative times that day: "
                    f"{', '.join(availability['alternatives'])}.")
        return "That new time isn't available and there are no other openings that day."

    updated = calendar_service.reschedule_event(
        event_id=existing["calendar_event_id"],
        date_str=args["new_date"], time_str=args["new_time"],
        duration_minutes=duration_minutes,
    )
    database.update_appointment_time(existing["id"], updated["start"], updated["end"])
    notifications.appointment_rescheduled({
        "patient_name": patient_name,
        "callback_number": callback_number,
        "date": args["new_date"],
        "time": args["new_time"],
        "email": existing.get("email"),
    })
    return f"Your appointment has been moved to {args['new_date']} at {args['new_time']}."


def _cancel_appointment(args: dict) -> str:
    patient_name = args["patient_name"]
    callback_number = args["callback_number"]

    existing = database.find_latest_booked_appointment(patient_name, callback_number)
    if not existing:
        return (f"I couldn't find an existing appointment for {patient_name} with that "
                "callback number. Could you double check the name and number?")

    calendar_service.cancel_event(existing["calendar_event_id"])
    database.mark_appointment_cancelled(existing["id"])
    notifications.appointment_cancelled({
        "patient_name": patient_name,
        "callback_number": callback_number,
        "email": existing.get("email"),
    })
    return "Your appointment has been cancelled."


# --- Leads and qualification ----------------------------------------------

def _capture_lead(args: dict) -> str:
    caller_name = args["caller_name"]
    callback_number = args["callback_number"]

    scored = qualification.score_lead(
        timeframe=args.get("timeframe"),
        intent=args.get("intent"),
        budget=args.get("budget"),
        contact_complete=bool(caller_name and callback_number),
    )

    lead = {
        "caller_name": caller_name,
        "callback_number": callback_number,
        "category": args.get("category", "enquiry"),
        "reason": args.get("reason", ""),
        "notes": args.get("notes", ""),
        "email": args.get("email"),
        "qualification": scored["band"],
        "qualification_score": scored["score"],
    }
    database.insert_lead(**lead)
    notifications.lead_captured(lead)

    if scored["band"] == "hot":
        return ("Got it, your details have been recorded and I've flagged this for our "
                "team to call you back as a priority.")
    return "Got it, your details have been recorded and someone will follow up."


# --- Customer support ------------------------------------------------------

def _answer_question(args: dict) -> str:
    entry = knowledge_base.search(args.get("question", ""))
    if entry:
        return entry["answer"]
    return ("I don't have a confirmed answer for that in our information. I can take your "
            "details and have a team member follow up, or raise a support ticket.")


def _create_support_ticket(args: dict) -> str:
    ticket_id = database.insert_support_ticket(
        caller_name=args["caller_name"],
        callback_number=args["callback_number"],
        issue=args["issue"],
        priority=args.get("priority", "normal"),
    )
    notifications.support_ticket_created({
        "id": ticket_id,
        "caller_name": args["caller_name"],
        "callback_number": args["callback_number"],
        "issue": args["issue"],
        "priority": args.get("priority", "normal"),
    })
    return (f"I've raised support ticket number {ticket_id} for you. Our team will follow "
            "up on it, and you can quote that number if you call back.")


# --- Receptionist / hours --------------------------------------------------

def _check_business_hours(args: dict) -> str:
    status = business_hours.status()
    if status["open"]:
        return (f"We're currently open. Local time is {status['local_time']}. "
                f"Our hours are {status['hours_summary']}.")
    return (f"We're currently closed — local time is {status['local_time']}. "
            f"We reopen {status['reopens_at']}. Our hours are {status['hours_summary']}. "
            "I can still book appointments, answer questions, or take a message.")


# --- Outbound follow-ups ---------------------------------------------------

def _schedule_followup(args: dict) -> str:
    followup_id = database.insert_followup(
        contact_name=args["contact_name"],
        phone_number=args["phone_number"],
        purpose=args["purpose"],
    )
    notifications.trigger_automation("followup.scheduled", {
        "id": followup_id,
        "contact_name": args["contact_name"],
        "phone_number": args["phone_number"],
        "purpose": args["purpose"],
    })
    return "I've scheduled a follow-up call for you and our team will reach out."
