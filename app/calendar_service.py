import datetime
import os
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]
BUSINESS_START_HOUR = config.BUSINESS_START_HOUR
BUSINESS_END_HOUR = config.BUSINESS_END_HOUR

_service = None


def _get_service():
    global _service
    if _service is None:
        key_path = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
        creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
        _service = build("calendar", "v3", credentials=creds)
    return _service


def _calendar_id():
    return os.environ["GOOGLE_CALENDAR_ID"]


def _tz():
    return ZoneInfo(os.environ.get("TIMEZONE", "UTC"))


def check_availability(date_str: str, time_str: str, duration_minutes: int = 30):
    tz = _tz()
    start = datetime.datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=tz)
    end = start + datetime.timedelta(minutes=duration_minutes)

    service = _get_service()
    calendar_id = _calendar_id()
    fb = service.freebusy().query(body={
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": calendar_id}],
    }).execute()
    busy = fb["calendars"][calendar_id]["busy"]

    if not busy:
        return {"available": True, "slot": start.isoformat(), "alternatives": []}

    alternatives = _find_alternative_slots(date_str, duration_minutes, tz, exclude_start=start)
    return {"available": False, "slot": start.isoformat(), "alternatives": alternatives}


def _find_alternative_slots(date_str, duration_minutes, tz, exclude_start, max_results=3):
    day_start = datetime.datetime.fromisoformat(f"{date_str}T00:00:00").replace(tzinfo=tz)
    window_start = day_start.replace(hour=BUSINESS_START_HOUR)
    window_end = day_start.replace(hour=BUSINESS_END_HOUR)

    service = _get_service()
    calendar_id = _calendar_id()
    fb = service.freebusy().query(body={
        "timeMin": window_start.isoformat(),
        "timeMax": window_end.isoformat(),
        "items": [{"id": calendar_id}],
    }).execute()
    busy_ranges = [
        (datetime.datetime.fromisoformat(b["start"]), datetime.datetime.fromisoformat(b["end"]))
        for b in fb["calendars"][calendar_id]["busy"]
    ]

    slots = []
    cursor = window_start
    step = datetime.timedelta(minutes=duration_minutes)
    while cursor + step <= window_end and len(slots) < max_results:
        slot_end = cursor + step
        overlaps = any(cursor < b_end and slot_end > b_start for b_start, b_end in busy_ranges)
        if not overlaps and cursor != exclude_start:
            slots.append(cursor.isoformat())
        cursor += step
    return slots


def book_appointment(patient_name: str, callback_number: str, appointment_type: str,
                      date_str: str, time_str: str, duration_minutes: int = 30):
    tz = _tz()
    start = datetime.datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=tz)
    end = start + datetime.timedelta(minutes=duration_minutes)

    service = _get_service()
    event = {
        "summary": f"{appointment_type} - {patient_name}",
        "description": f"Booked via AI voice agent. Callback number: {callback_number}",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    created = service.events().insert(calendarId=_calendar_id(), body=event).execute()
    return {"event_id": created["id"], "start": start.isoformat(), "end": end.isoformat()}


def reschedule_event(event_id: str, date_str: str, time_str: str, duration_minutes: int = 30):
    tz = _tz()
    start = datetime.datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=tz)
    end = start + datetime.timedelta(minutes=duration_minutes)

    service = _get_service()
    updated = service.events().patch(
        calendarId=_calendar_id(),
        eventId=event_id,
        body={
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        },
    ).execute()
    return {"event_id": updated["id"], "start": start.isoformat(), "end": end.isoformat()}


def cancel_event(event_id: str):
    service = _get_service()
    service.events().delete(calendarId=_calendar_id(), eventId=event_id).execute()
