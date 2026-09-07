"""Outbound notifications: Slack alerts, caller emails, CRM sync, automation hooks.

Every function no-ops safely (logging instead) when its integration isn't
configured, so the call flow never breaks because a webhook is missing.
"""

import json
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from app import config


def _post_json(url: str, payload: dict, label: str) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as exc:
        print(f"[{label} failed] {exc}")
        return False


def notify_slack(text: str) -> bool:
    """Alert the internal team in Slack via an incoming webhook."""
    url = config.slack_webhook_url()
    if not url:
        print(f"[slack skipped - SLACK_WEBHOOK_URL not set] {text}")
        return False
    return _post_json(url, {"text": text}, "slack")


def trigger_automation(event: str, data: dict) -> bool:
    """Fire a generic webhook so Zapier/Make/n8n can run downstream workflows."""
    url = config.automation_webhook_url()
    if not url:
        print(f"[automation skipped - AUTOMATION_WEBHOOK_URL not set] {event}")
        return False
    return _post_json(url, {"event": event, "data": data}, "automation")


def sync_to_crm(record_type: str, data: dict) -> bool:
    """Push a contact/appointment into the CRM (e.g. GoHighLevel inbound webhook)."""
    url = config.crm_webhook_url()
    if not url:
        print(f"[crm skipped - CRM_WEBHOOK_URL not set] {record_type}")
        return False
    return _post_json(url, {"type": record_type, **data}, "crm")


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email (caller confirmation, or sales-team alert)."""
    if not to_email:
        return False

    smtp = config.smtp_settings()
    if not all([smtp["host"], smtp["port"], smtp["user"], smtp["password"]]):
        print(f"[email skipped - SMTP not configured] to={to_email} subject={subject}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp["sender"]
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=10) as server:
            server.starttls()
            server.login(smtp["user"], smtp["password"])
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[email failed] {exc}")
        return False


# --- Composed notifications used by the call flow --------------------------

def appointment_booked(appointment: dict) -> None:
    summary = (
        f"📅 New appointment: {appointment['patient_name']} — "
        f"{appointment['appointment_type']} on {appointment['date']} at {appointment['time']} "
        f"(callback: {appointment['callback_number']})"
    )
    notify_slack(summary)
    sync_to_crm("appointment", appointment)
    trigger_automation("appointment.booked", appointment)

    if appointment.get("email"):
        send_email(
            appointment["email"],
            f"Your appointment with {config.BUSINESS_NAME} is confirmed",
            f"Hi {appointment['patient_name']},\n\n"
            f"Your {appointment['appointment_type']} appointment is confirmed for "
            f"{appointment['date']} at {appointment['time']}.\n\n"
            "Please arrive 15 minutes early (20 minutes if this is your first visit) and bring "
            "your insurance card, photo ID, and a list of any medications.\n\n"
            "If you need to reschedule or cancel, just call us back.\n\n"
            f"— {config.BUSINESS_NAME}",
        )


def appointment_rescheduled(appointment: dict) -> None:
    notify_slack(
        f"🔄 Appointment rescheduled: {appointment['patient_name']} moved to "
        f"{appointment['date']} at {appointment['time']} (callback: {appointment['callback_number']})"
    )
    sync_to_crm("appointment", appointment)
    trigger_automation("appointment.rescheduled", appointment)

    if appointment.get("email"):
        send_email(
            appointment["email"],
            f"Your appointment with {config.BUSINESS_NAME} has been rescheduled",
            f"Hi {appointment['patient_name']},\n\n"
            f"Your appointment has been moved to {appointment['date']} at {appointment['time']}.\n\n"
            f"— {config.BUSINESS_NAME}",
        )


def appointment_cancelled(appointment: dict) -> None:
    notify_slack(
        f"❌ Appointment cancelled: {appointment['patient_name']} "
        f"(callback: {appointment['callback_number']})"
    )
    sync_to_crm("appointment_cancelled", appointment)
    trigger_automation("appointment.cancelled", appointment)

    if appointment.get("email"):
        send_email(
            appointment["email"],
            f"Your appointment with {config.BUSINESS_NAME} has been cancelled",
            f"Hi {appointment['patient_name']},\n\n"
            "This confirms your appointment has been cancelled as requested.\n\n"
            f"— {config.BUSINESS_NAME}",
        )


def lead_captured(lead: dict) -> None:
    heat = lead.get("qualification", "unscored")
    icon = {"hot": "🔥", "warm": "🌤️", "cold": "❄️"}.get(heat, "📇")
    summary = (
        f"{icon} New {heat} lead: {lead['caller_name']} ({lead['callback_number']}) — "
        f"{lead.get('reason', 'no reason given')} [{lead.get('category', 'enquiry')}]"
    )
    notify_slack(summary)
    sync_to_crm("lead", lead)
    trigger_automation("lead.captured", lead)

    # Qualified leads also go to the sales team inbox directly.
    if heat == "hot" and config.sales_team_email():
        send_email(
            config.sales_team_email(),
            f"Qualified lead: {lead['caller_name']}",
            f"{summary}\n\nNotes: {lead.get('notes', '')}\n"
            f"Qualification score: {lead.get('qualification_score', 'n/a')}",
        )


def support_ticket_created(ticket: dict) -> None:
    notify_slack(
        f"🎫 Support ticket #{ticket['id']}: {ticket['caller_name']} — {ticket['issue']} "
        f"(priority: {ticket['priority']})"
    )
    sync_to_crm("support_ticket", ticket)
    trigger_automation("support_ticket.created", ticket)


def call_summary_ready(summary: dict) -> None:
    notify_slack(
        f"📝 Call summary [{summary.get('call_id', 'unknown')}]: {summary.get('summary', '')[:300]}"
    )
    trigger_automation("call.summarized", summary)
