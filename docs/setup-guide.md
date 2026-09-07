# Zephvion AI Voice Agent — Setup & Operations Guide

A complete AI voice agent that answers calls 24/7, books/reschedules/cancels appointments on a real calendar, answers questions about the business, captures and qualifies leads, raises support tickets, escalates to humans, and makes outbound follow-up calls.

**Every component below runs on a free tier. No paid service is required.**

---

## 1. What the system does

| Capability | How it works |
|---|---|
| Answers incoming calls | AI voice agent (Vapi) with a custom conversation design |
| Books appointments | Checks real availability and creates events on Google Calendar |
| Reschedules / cancels | Moves or deletes the real calendar event, updates records |
| Answers questions | Searches a business knowledge base for confirmed answers |
| Captures & qualifies leads | Scores each enquiry hot / warm / cold from the caller's answers |
| Raises support tickets | Creates a numbered ticket and alerts the team |
| Works 24/7 | Detects out-of-hours calls and adapts what it tells the caller |
| Escalates to a human | Transfers the live call, or logs a callback request |
| Post-call summaries | Stores a summary, transcript and outcome for every call |
| Notifies the team | Slack alerts and email for bookings, leads and tickets |
| Syncs to CRM | Pushes contacts and bookings to any webhook-capable CRM |
| Triggers automations | Fires events to Zapier / Make / n8n for downstream workflows |
| Outbound calling | Appointment reminders, follow-ups and re-engagement calls |

---

## 2. Technology used (and why each is free)

| Component | Service | Free tier |
|---|---|---|
| Voice AI agent | Vapi | Free credits, free test phone number |
| Telephony | Vapi built-in number | Included free (US number) |
| Calendar | Google Calendar API | Completely free |
| Backend | Python + FastAPI | Open source |
| Database | SQLite | Open source, no server needed |
| Public tunnel (dev) | ngrok | Free tier |
| Team alerts | Slack incoming webhook | Free on any Slack workspace |
| Email | Gmail SMTP | Free (500 emails/day) |
| CRM | HubSpot free CRM or Google Sheets | Both genuinely free |
| Automation | Zapier / Make / n8n | All have free tiers |

> **Note on GoHighLevel:** the original specification names GoHighLevel as a CRM option, but it has no free tier (~$97/month). The CRM sync is built as a **generic webhook**, so it works with GoHighLevel *or* any free alternative (HubSpot free, Google Sheets via Apps Script) by changing one environment variable. No code changes needed.

---

## 3. First-time setup

### 3.1 Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3.2 Google Calendar (required)

1. Go to console.cloud.google.com and log in.
2. Create a new project.
3. APIs & Services → Library → search "Google Calendar API" → **Enable**.
4. APIs & Services → Credentials → Create Credentials → **Service Account** → name it → create.
5. Open the service account → **Keys** → Add Key → Create New Key → **JSON** → download.
6. Save that file into the project folder as `service-account.json`.
7. Open Google Calendar → the target calendar's settings → **Share with specific people** → add the service account's email (found inside the JSON file) with **"Make changes to events"**.
8. Same settings page → **Integrate calendar** → copy the **Calendar ID**.
9. In `.env`, set `GOOGLE_CALENDAR_ID` to that value and `TIMEZONE` to your timezone.

### 3.3 Run it

```bash
source .venv/bin/activate
uvicorn app.main:app --port 8000
```

In a second terminal:

```bash
ngrok http 8000
```

Copy the `https://....ngrok-free.app` URL — this is your public server URL.

---

## 4. Vapi configuration

### 4.1 Assistant

1. Sign up at vapi.ai, open the Dashboard.
2. Create an agent → choose **Inbound**.
3. Paste the contents of `prompts/system_prompt.md` (everything from "## Identity & Purpose") into the **System Prompt** field.
4. Set **First Message** to: *"Thank you for calling Wellness Partners. This is Riley, your scheduling assistant. How may I help you today?"*

### 4.2 Phone number

1. Phone Numbers → Create Phone Number → **Free Vapi Number** → enter a US area code → Create.
2. Open the number → **Inbound Settings** → assign your assistant → Save.

### 4.3 Tools (9 total)

Tools → Create Tool, for each one below. Set **Type** = Function, **Server URL** = `https://<your-ngrok-url>/tools/webhook`, and increase the **timeout** in Advanced Settings to ~20 seconds (calendar calls need headroom).

| Function name | Parameters (required in **bold**) |
|---|---|
| `check_availability` | **date**, **time**, duration_minutes |
| `book_appointment` | **patient_name**, **callback_number**, **appointment_type**, **date**, **time**, email, duration_minutes |
| `reschedule_appointment` | **patient_name**, **callback_number**, **new_date**, **new_time**, duration_minutes |
| `cancel_appointment` | **patient_name**, **callback_number** |
| `capture_lead` | **caller_name**, **callback_number**, **category**, **reason**, notes, email, timeframe, intent, budget |
| `answer_question` | **question** |
| `create_support_ticket` | **caller_name**, **callback_number**, **issue**, priority |
| `check_business_hours` | *(none)* |
| `schedule_followup` | **contact_name**, **phone_number**, **purpose** |

All parameters are strings except `duration_minutes` (number).

Then: Assistants → your assistant → **Tools** tab → add all 9 → Save.

### 4.4 Live call transfer (escalation)

1. Tools → Create Tool → select the **Transfer Call** tool type.
2. Set the destination to the phone number a human should receive transfers on.
3. Add it to the assistant alongside the other tools.

### 4.5 Post-call summaries

1. In the assistant settings, find **Server URL** (server messages/webhooks).
2. Set it to `https://<your-ngrok-url>/webhooks/vapi`.
3. Enable the **end-of-call-report** server message.

Every completed call will then be stored with its summary, transcript, duration and end reason.

### 4.6 Multilingual (optional)

In the assistant's transcriber settings, enable multilingual/auto language detection, and choose a voice that supports the target language. For Indian-accented English, Azure's `en-IN-NeerjaNeural` or `en-IN-PrabhatNeural` work well and need no separate API key.

---

## 5. Optional integrations (all free)

Fill these into `.env` — each one is independent, and anything left blank is simply skipped.

### Slack alerts
Slack → your workspace → Apps → **Incoming Webhooks** → add to a channel → copy the webhook URL → set `SLACK_WEBHOOK_URL`.

### Email confirmations
1. Google Account → Security → enable 2-Step Verification.
2. Then Security → **App Passwords** → generate one for "Mail".
3. Set `SMTP_USER` to your Gmail address and `SMTP_PASSWORD` to that app password.
4. Set `SALES_TEAM_EMAIL` to whoever should receive qualified-lead alerts.

### CRM sync
- **HubSpot (free):** create a free account, then use a workflow/webhook endpoint as `CRM_WEBHOOK_URL`.
- **Google Sheets (free):** create a Sheet → Extensions → Apps Script → publish a `doPost` web app → use its URL as `CRM_WEBHOOK_URL`.

### Workflow automation
Create a "Catch Hook" (Zapier) or "Custom Webhook" (Make) trigger, and set `AUTOMATION_WEBHOOK_URL` to it. Events fired: `appointment.booked`, `appointment.rescheduled`, `appointment.cancelled`, `lead.captured`, `support_ticket.created`, `call.summarized`, `followup.scheduled`.

---

## 6. Daily operation

**View everything captured:**
```bash
python3 view_data.py
```
Shows appointments, leads (with qualification), support tickets, call summaries and the follow-up queue.

**Outbound calling:**
```bash
python3 outbound_calls.py reminders    # call tomorrow's appointments
python3 outbound_calls.py followups    # work the pending follow-up queue
python3 outbound_calls.py call +911234567890 "reason for this call"
```
Requires `VAPI_API_KEY`, `VAPI_ASSISTANT_ID` and `VAPI_PHONE_NUMBER_ID` in `.env`.

---

## 7. Customising for a different business

The system is business-agnostic — adapting it takes three edits, no code changes:

1. **`knowledge_base.json`** — replace the FAQ entries with the new business's information.
2. **`prompts/system_prompt.md`** — change the persona, business name and conversation paths.
3. **`.env`** — set `BUSINESS_NAME`, opening hours, days and timezone.

---

## 8. Project structure

```
app/
  main.py               FastAPI application entry point
  config.py             All settings, read from environment variables
  database.py           SQLite storage and schema migrations
  calendar_service.py   Google Calendar availability, booking, moving, cancelling
  business_hours.py     Open/closed logic for 24/7 receptionist behaviour
  qualification.py      Lead scoring (hot / warm / cold)
  knowledge_base.py     FAQ search for customer support answers
  notifications.py      Slack, email, CRM sync, automation webhooks
  routes/
    tools.py            Receives the AI's tool calls, runs the business logic
    webhooks.py         Receives end-of-call reports for summaries
knowledge_base.json     The business's FAQ content
prompts/system_prompt.md  The AI agent's instructions
view_data.py            Readable view of all captured data
outbound_calls.py       Outbound reminder / follow-up calling
docs/                   Progress report, conversation flow, these guides
```

---

## 9. Known limitations

- **ngrok free tier** gives a new public URL each restart, so the tool Server URLs must be updated when it restarts. For continuous operation the backend should be deployed to a persistent host.
- **Vapi free credits** are limited; heavy call testing will exhaust them.
- **Vapi's free number is US-based**, so calling it from India incurs international charges. Browser-based testing ("Talk") avoids this entirely and exercises identical logic.
- The knowledge base uses keyword matching over a curated FAQ set. This is deliberate — it keeps answers accurate and prevents the agent inventing policies — but it only answers what has been written into it.
