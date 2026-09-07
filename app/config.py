"""Central configuration, read from environment variables.

Everything here has a sensible default so the app runs even when optional
integrations (Slack, email, CRM, automation) are not configured yet.
"""

import os
from zoneinfo import ZoneInfo

# --- Business identity -----------------------------------------------------
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Wellness Partners")

# --- Scheduling ------------------------------------------------------------
BUSINESS_START_HOUR = int(os.environ.get("BUSINESS_START_HOUR", 9))
BUSINESS_END_HOUR = int(os.environ.get("BUSINESS_END_HOUR", 17))
# Monday=0 ... Sunday=6. Default: Mon-Fri, plus Saturday morning.
BUSINESS_DAYS = [int(d) for d in os.environ.get("BUSINESS_DAYS", "0,1,2,3,4,5").split(",")]
SATURDAY_END_HOUR = int(os.environ.get("SATURDAY_END_HOUR", 12))

DEFAULT_APPOINTMENT_MINUTES = int(os.environ.get("DEFAULT_APPOINTMENT_MINUTES", 30))


def timezone():
    return ZoneInfo(os.environ.get("TIMEZONE", "UTC"))


# --- Integrations (all optional) -------------------------------------------
def slack_webhook_url():
    return os.environ.get("SLACK_WEBHOOK_URL")


def automation_webhook_url():
    """Generic outgoing webhook for Zapier / Make / n8n style automations."""
    return os.environ.get("AUTOMATION_WEBHOOK_URL")


def smtp_settings():
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": os.environ.get("SMTP_PORT"),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "sender": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER"),
    }


def sales_team_email():
    return os.environ.get("SALES_TEAM_EMAIL")


def crm_webhook_url():
    """GoHighLevel (or any CRM) inbound webhook for contact/opportunity sync."""
    return os.environ.get("CRM_WEBHOOK_URL")


def escalation_phone_number():
    """Number a live call is transferred to when a human is needed."""
    return os.environ.get("ESCALATION_PHONE_NUMBER")


# --- Vapi (for outbound calling) -------------------------------------------
def vapi_api_key():
    return os.environ.get("VAPI_API_KEY")


def vapi_assistant_id():
    return os.environ.get("VAPI_ASSISTANT_ID")


def vapi_phone_number_id():
    return os.environ.get("VAPI_PHONE_NUMBER_ID")
