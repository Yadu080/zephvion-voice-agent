"""Scheduled task endpoints.

Point a free cron service (cron-job.org, GitHub Actions, etc.) at these so
reminders and follow-ups run automatically instead of being typed by hand.

They live on the server because that is where the database and the Vapi
credentials already are.

Each request must carry the shared token, either as `?token=...` or an
`X-Tasks-Token` header. Without TASKS_TOKEN set, the endpoints stay disabled
rather than defaulting to open — they can spend money by placing calls.
"""

import os

from fastapi import APIRouter, HTTPException, Request

from app import business_hours, outbound

router = APIRouter()


def _authorize(request: Request) -> None:
    expected = os.environ.get("TASKS_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Scheduled tasks are disabled. Set TASKS_TOKEN to enable them.",
        )

    supplied = (request.headers.get("X-Tasks-Token")
                or request.query_params.get("token"))
    if supplied != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing task token.")


@router.post("/tasks/reminders")
async def run_reminders(request: Request, days_ahead: int = 1, force: bool = False):
    """Call tomorrow's appointments to confirm attendance."""
    _authorize(request)

    # Don't cold-call people outside business hours unless explicitly forced.
    if not business_hours.is_open() and not force:
        return {"skipped": "outside business hours",
                "hint": "pass force=true to override"}

    return outbound.appointment_reminders(days_ahead=days_ahead)


@router.post("/tasks/followups")
async def run_followups(request: Request, force: bool = False):
    """Work through the pending follow-up queue."""
    _authorize(request)

    if not business_hours.is_open() and not force:
        return {"skipped": "outside business hours",
                "hint": "pass force=true to override"}

    return outbound.work_followup_queue()
