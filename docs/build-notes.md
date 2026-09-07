# Build Notes (personal — not for submission)

Working notes on things researched/designed but not yet built, to pick up later.

---

## STATUS as of 2026-09-07: everything below is now BUILT

The notifications/confirmations work described further down was un-parked and implemented,
along with the rest of the spec. Current state of the code:

**Built and locally tested:**
- `app/config.py` — all settings via env, every integration optional
- `app/notifications.py` — Slack, email (Gmail SMTP), CRM webhook, automation webhook
- `app/business_hours.py` — open/closed, next opening, hours summary
- `app/qualification.py` — lead scoring → hot/warm/cold
- `app/knowledge_base.py` + `knowledge_base.json` — keyword FAQ search
- `app/routes/webhooks.py` — end-of-call-report → call summaries
- `outbound_calls.py` — reminders / followup queue / single call via Vapi API
- 9 tools total in `app/routes/tools.py`
- DB: added `email`, `qualification`, `qualification_score` on leads; new tables
  `support_tickets`, `call_summaries`, `followups` (all migration-safe)

**NOT yet done (needs dashboard work / user credentials):**
- Registering the 4 new tools in Vapi (`answer_question`, `create_support_ticket`,
  `check_business_hours`, `schedule_followup`)
- Transfer Call tool for live escalation
- Assistant Server URL → `/webhooks/vapi` + enable end-of-call-report
- Filling in `SLACK_WEBHOOK_URL`, SMTP creds, `CRM_WEBHOOK_URL`, `AUTOMATION_WEBHOOK_URL`
- Live end-to-end retest of all paths

---

## RESOLVED: cancellation reported as failed

**Root cause found 2026-09-07.** It was NOT a timeout (the earlier theory).

`find_latest_booked_appointment` used `WHERE patient_name = ? AND callback_number = ?` —
an exact match on both. In the demo call the number was read back as "819-728-8398" but
stored as "8197288398", so the lookup returned nothing → tool replied "couldn't find an
appointment" → the LLM escalated saying "system issue".

Confirmed against the real DB: of 4 realistic input variations, the old lookup matched
only 1; the new one matches all 4.

**Fix:** lookup now compares last-10 digits only, and prefers an exact name+phone match
but falls back to either matching. Also added an instruction to the system prompt not to
invent dash formatting when reading numbers back.

**Still worth doing anyway:** raise the Vapi tool timeouts to ~20s, since ngrok + Google
Calendar latency remains a real risk independent of this bug.

---

## Notifications & confirmations (parked for a future day)

**Findings:**
- Vapi's native `sms` tool requires a configured Twilio account — not usable since Twilio is out of scope for this build.
- Vapi has a native Slack Send Message tool (OAuth-connect + dashboard tool), but it's LLM-triggered mid-conversation — less reliable than firing it directly from our backend right when a booking/lead action actually succeeds.

**Planned approach when we pick this up:**
- Internal team alert → Slack **Incoming Webhook** (simple POST from our backend, no OAuth), triggered inside `book_appointment` / `reschedule_appointment` / `cancel_appointment` / `capture_lead` right after the DB/calendar action succeeds — not left to the LLM to remember.
- Caller confirmation → **email** instead of SMS (since SMS needs Twilio). Requires collecting an optional `email` field during booking (small addition to the conversation flow and tool schema), plus SMTP config (Gmail app password) for actually sending.
- New `app/notifications.py` module: `notify_slack(text)` and `send_confirmation_email(to, subject, body)`, both no-op safely if not configured (so nothing breaks if the env vars aren't set yet).
- DB schema needs an `email` column on `leads` and `appointments` (nullable, migration-safe via `ALTER TABLE ... ADD COLUMN` since the DB already has real test data).
- New env vars needed: `SLACK_WEBHOOK_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

This was scoped, drafted, and reverted on 2026-08-31 — revisit when ready to actually wire it up (needs a Slack webhook URL and a Gmail app password from you first).

---

## Unresolved: cancellation reported as failed even though it succeeded

**Status: open, not yet confirmed.**

Observed in a live demo call (see transcript in the progress report): caller asked to cancel an appointment, the AI said "I wasn't able to process the cancellation just now due to a system issue" and escalated to a human — but the appointment was actually cancelled successfully (calendar event removed, DB row updated).

**Leading theory:** the backend completed the cancellation correctly, but Vapi's tool call timed out waiting for the response before it arrived (likely due to ngrok free-tier latency + Google Calendar API round-trip), so Vapi told the AI the call failed even though our server had already succeeded.

**To confirm, still need to check (asked user, not yet reported back):**
1. ngrok's local inspector (`http://127.0.0.1:4040`) — find the `/tools/webhook` request for that cancel call, check its status code and duration.
2. The uvicorn terminal log for that same request — did it show `200 OK` with the success message, or an exception?

**If confirmed as a timeout:** fix is to increase the **Timeout Settings** on each tool in the Vapi dashboard (Tools → each tool → Advanced Settings → raise timeout to ~15-20s) to give Google Calendar + ngrok enough headroom.

**Also worth reconsidering long-term:** ngrok free tier is a real reliability risk for anything beyond casual testing/demo — a proper deployment (even a cheap always-on host) would remove this whole class of bug.

---

## Voice / accent configuration

**Goal:** make Riley sound more natural and Indian-accented.

**What was tried:**
- ElevenLabs voice + pronunciation dictionary (for fixing name pronunciation, e.g. caller names like "Nimbalkar") — requires **your own ElevenLabs API key** connected in Vapi (Provider Keys), not bundled.
- Hit `pipeline-error-eleven-labs-voice-failed` after adding the key — root cause was the API key's permissions: **Text to Speech** endpoint access was not enabled on the key. Fixed by regenerating the key with Text to Speech set to "Access" instead of "No Access."
- If it still fails after that fix, remaining free-tier ElevenLabs risks: voice not included in free tier's accessible voice set, or monthly character quota (~10,000 chars) exhausted.

**Fallback if ElevenLabs remains flaky:** Azure's Indian English neural voices, bundled through Vapi without needing a separate API key —`en-IN-NeerjaNeural` (female) or `en-IN-PrabhatNeural` (male). Simpler, no quota/permission risk, still natural-sounding.

**Not yet confirmed:** whether the ElevenLabs fix actually resolved the voice pipeline error — need to test via Talk again.

---

## Newly identified doc-fidelity gaps (added to the official "What's Left" list, noting build approach here)

- **After-hours / 24-7 receptionist behavior.** The spec explicitly describes different behavior when called outside business hours (provide company info, capture a message) — not currently distinguished from a normal in-hours call. Would need: business-hours config (start/end times, days), a check at call start or in the system prompt logic, and a distinct greeting/flow for after-hours calls.
- **Workflow automation platform integration** (Zapier/Make-style). Not started. Likely simplest approach: a generic outgoing webhook fired from the same points as the (parked) Slack notification, so leads/bookings can trigger downstream automations without hardcoding to one platform.
