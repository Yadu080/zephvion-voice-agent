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


# End reasons that mean we never actually spoke to the person, so an
# outbound follow-up should go back in the queue rather than be closed out.
UNREACHED_REASONS = (
    "no-answer", "busy", "voicemail", "customer-did-not-answer",
    "customer-busy", "failed", "twilio-failed", "vapi-error",
)


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

    _close_outbound_workflow(message, call, summary, ended_reason)


def _close_outbound_workflow(message: dict, call: dict, summary: str,
                             ended_reason: str | None) -> None:
    """If this was an outbound call we placed, record the outcome against the
    follow-up it came from and trigger the appropriate next action."""
    metadata = call.get("metadata") or message.get("metadata") or {}
    followup_id = metadata.get("followup_id")
    if not followup_id:
        return

    followup = database.get_followup(followup_id)
    if not followup:
        return

    reason = (ended_reason or "").lower()
    unreached = any(marker in reason for marker in UNREACHED_REASONS)

    if unreached:
        database.requeue_followup(
            followup_id, f"Not reached ({ended_reason}) — queued to try again"
        )
        notifications.notify_slack(
            f"📞 Follow-up to {followup['contact_name']} didn't connect "
            f"({ended_reason}) — back in the queue."
        )
        notifications.trigger_automation("followup.unreached", {
            "followup_id": followup_id,
            "contact_name": followup["contact_name"],
            "phone_number": followup["phone_number"],
            "ended_reason": ended_reason,
        })
        return

    outcome = summary or f"Call completed ({ended_reason})"
    database.complete_followup(followup_id, outcome)
    notifications.notify_slack(
        f"✅ Follow-up completed with {followup['contact_name']}: {outcome[:250]}"
    )
    notifications.trigger_automation("followup.completed", {
        "followup_id": followup_id,
        "contact_name": followup["contact_name"],
        "phone_number": followup["phone_number"],
        "purpose": followup["purpose"],
        "outcome": outcome,
    })
