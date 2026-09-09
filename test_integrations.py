"""Check which integrations are configured, and actually exercise them.

Sends a real test message through each one that's set up, so you find out
now rather than during a live call.

Usage:
    python3 test_integrations.py            # report what's configured
    python3 test_integrations.py --send     # also send real test messages
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from app import config, notifications  # noqa: E402

SEND = "--send" in sys.argv


def check(label, configured, sender=None, note=""):
    if not configured:
        print(f"  [ ] {label:22} not configured{('  — ' + note) if note else ''}")
        return

    if not SEND or sender is None:
        print(f"  [x] {label:22} configured")
        return

    ok = sender()
    print(f"  [{'x' if ok else '!'}] {label:22} "
          f"{'test sent successfully' if ok else 'CONFIGURED BUT FAILED — see error above'}")


def main():
    smtp = config.smtp_settings()
    smtp_ready = all([smtp["host"], smtp["port"], smtp["user"], smtp["password"]])

    print("\nIntegration status")
    print("=" * 60)

    check("Slack alerts", bool(config.slack_webhook_url()),
          lambda: notifications.notify_slack(
              "Test from the Zephvion voice agent — Slack alerts are working."),
          "team won't be alerted to bookings, leads or tickets")

    check("Email (SMTP)", smtp_ready,
          lambda: notifications.send_email(
              smtp["user"],
              "Zephvion voice agent — test email",
              "If you're reading this, caller confirmation emails are working."),
          "callers get no booking confirmation")

    check("Sales team email", bool(config.sales_team_email()),
          lambda: notifications.send_email(
              config.sales_team_email(),
              "Zephvion voice agent — qualified lead alert test",
              "If you're reading this, qualified-lead alerts are working.")
          if smtp_ready else None,
          "qualified leads won't be emailed to sales")

    check("CRM sync", bool(config.crm_webhook_url()),
          lambda: notifications.sync_to_crm("test", {
              "note": "Test from the Zephvion voice agent"}),
          "contacts and bookings won't reach a CRM")

    check("Workflow automation", bool(config.automation_webhook_url()),
          lambda: notifications.trigger_automation("test.event", {
              "note": "Test from the Zephvion voice agent"}),
          "no downstream automations will fire")

    print()
    print("Calling")
    print("=" * 60)
    check("Outbound calling", bool(config.vapi_api_key()
                                   and config.vapi_assistant_id()
                                   and config.vapi_phone_number_id()),
          None, "reminders and follow-up calls can't be placed")
    check("Live transfer number", bool(config.escalation_phone_number()),
          None, "set in the Vapi transfer tool instead, if not here")

    if not SEND:
        print("\nRun with --send to actually send test messages through each one.")
    print()


if __name__ == "__main__":
    main()
