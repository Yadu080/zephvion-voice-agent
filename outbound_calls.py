"""Outbound calling from the command line — reminders, follow-ups, one-offs.

The scheduled versions of these run on the server (see app/routes/tasks.py);
this is for running them by hand.

Usage:
    python3 outbound_calls.py reminders                    # call tomorrow's appointments
    python3 outbound_calls.py followups                    # work the pending queue
    python3 outbound_calls.py call +919876543210 "reason"  # one-off call

Requires VAPI_API_KEY, VAPI_ASSISTANT_ID and VAPI_PHONE_NUMBER_ID in .env.
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from app import outbound  # noqa: E402  (must load env first)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    if command == "reminders":
        print(outbound.appointment_reminders())
    elif command == "followups":
        print(outbound.work_followup_queue())
    elif command == "call" and len(sys.argv) >= 4:
        outbound.place_call(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
