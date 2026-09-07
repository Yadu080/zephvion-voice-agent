"""Vapi server webhooks — currently the end-of-call report, which gives us
post-call summaries and structured conversation data.

Point Vapi's assistant "Server URL" at /webhooks/vapi and enable the
end-of-call-report server message.
"""

from fastapi import APIRouter, Request

from app import database, notifications

router = APIRouter()


@router.post("/webhooks/vapi")
async def vapi_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})
    event_type = message.get("type")

    if event_type == "end-of-call-report":
        _handle_end_of_call(message)

    # Vapi only needs a 200; other event types are accepted and ignored.
    return {"received": True}


def _handle_end_of_call(message: dict) -> None:
    call = message.get("call") or {}
    artifact = message.get("artifact") or {}

    summary = message.get("summary") or artifact.get("summary") or ""
    transcript = message.get("transcript") or artifact.get("transcript") or ""
    call_id = call.get("id") or message.get("callId") or ""
    caller_number = (
        (call.get("customer") or {}).get("number")
        or message.get("customer", {}).get("number")
        or ""
    )
    ended_reason = message.get("endedReason") or call.get("endedReason")
    duration = message.get("durationSeconds") or message.get("duration")

    database.insert_call_summary(
        call_id=call_id,
        caller_number=caller_number,
        summary=summary,
        transcript=transcript if isinstance(transcript, str) else str(transcript),
        ended_reason=ended_reason,
        duration_seconds=float(duration) if duration is not None else None,
    )

    notifications.call_summary_ready({
        "call_id": call_id,
        "caller_number": caller_number,
        "summary": summary,
        "ended_reason": ended_reason,
        "duration_seconds": duration,
    })
