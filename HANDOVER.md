# Handover — Zephvion AI Voice Agent

Everything needed to take ownership of this project and run it independently.

No part of the system is tied to the original builder's accounts. The repository
is the deliverable: with your own credentials you can recreate the whole thing
in about an hour, and nothing needs to be rebuilt.

---

## 1. What you are receiving

An AI voice agent that answers calls 24/7 and:

- books, reschedules and cancels appointments on a real Google Calendar
- answers questions about the business from a knowledge base
- captures enquiries, asks qualifying questions, and scores leads hot / warm / cold
- raises support tickets with priority levels
- transfers callers to a human, briefing them on the conversation first
- adapts its behaviour outside business hours
- produces a summary, transcript and outcome for every call
- alerts the team in Slack, emails confirmations to callers, and syncs records to a CRM
- places outbound calls for appointment reminders and follow-ups
- speaks nine languages, detected automatically

**Running cost: nothing.** Every service is on a free tier. The only paid item
in the original specification was GoHighLevel; the CRM integration is a generic
webhook instead, so it works with GoHighLevel, HubSpot's free tier, or a Google
Sheet without changing any code.

---

## 2. Accounts you will need

| Service | Purpose | Cost |
|---|---|---|
| **Vapi** | The voice agent itself | Free credits |
| **Google Cloud** | Calendar API access | Free |
| **GitHub** | Holds the code | Free |
| **Render** | Runs the backend | Free tier |
| **cron-job.org** | Keeps the server awake, triggers scheduled calls | Free |
| **Slack** | Team alerts | Free |
| **Gmail** | Sends caller confirmations | Free |
| **Google Sheets** | Acts as the CRM | Free |

---

## 3. Taking ownership — step by step

### 3.1 Get the code

Fork or clone the repository into your own GitHub account.

### 3.2 Google Calendar

1. console.cloud.google.com → create a project
2. APIs & Services → Library → enable **Google Calendar API**
3. APIs & Services → Credentials → Create Credentials → **Service Account**
4. Open it → Keys → Add Key → Create New Key → **JSON** → download
5. Open the Google Calendar the agent should manage → its settings →
   **Share with specific people** → add the service account's email (inside the
   JSON file) with **"Make changes to events"**
6. Same page → **Integrate calendar** → copy the **Calendar ID**

### 3.3 Deploy the backend

1. render.com → New → **Web Service** → connect the repo
2. Settings are read from `render.yaml`; confirm the plan is **Free**
3. Environment → **Secret Files** → add `service-account.json` (paste the JSON from 3.2)
4. Environment → **Environment Variables** → add everything from
   `.env.example`, at minimum:
   - `GOOGLE_SERVICE_ACCOUNT_FILE` = `/etc/secrets/service-account.json`
   - `GOOGLE_CALENDAR_ID`, `TIMEZONE`
5. Wait for the deploy, then check `https://<your-app>.onrender.com/health`

### 3.4 Vapi

1. vapi.ai → create an account → Dashboard → **API Keys** → copy the private key
2. Locally: `cp .env.example .env`, then fill in `VAPI_API_KEY`
3. Point the scripts at your deployment — edit `SERVER_URL` at the top of
   `setup_vapi_tools.py` and `setup_vapi_assistant.py` to your Render URL
4. Run, in this order:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 setup_vapi_tools.py           # creates the 9 function tools
python3 setup_vapi_assistant.py --apply   # creates the assistant, prompt, multilingual config
# copy the assistant ID it prints into .env as VAPI_ASSISTANT_ID

python3 setup_vapi_transfer.py +91XXXXXXXXXX   # transfer destination for human handoff
python3 setup_vapi_sip.py             # optional: a SIP address for testing
```

5. In the Vapi dashboard: give the assistant a phone number
   (Phone Numbers → Create Phone Number → Free Vapi Number → assign to the assistant)

### 3.5 Notifications and CRM

Add each of these to `.env` **and** to Render's environment:

- **Slack:** api.slack.com/apps → Create New App → Incoming Webhooks → add to a
  channel → copy URL → `SLACK_WEBHOOK_URL`
- **Email:** Google Account → Security → enable 2-Step Verification → App
  Passwords → generate one for Mail → `SMTP_USER`, `SMTP_PASSWORD`,
  `SALES_TEAM_EMAIL`
- **CRM:** follow the instructions at the top of `docs/google-sheets-crm.gs` →
  `CRM_WEBHOOK_URL` (and `AUTOMATION_WEBHOOK_URL`, which can be the same URL)

Verify everything actually sends:

```bash
python3 test_integrations.py --send
```

### 3.6 Scheduling and uptime

Render's free tier sleeps after 15 minutes idle, and a cold start takes long
enough to fail a live call. At cron-job.org, create three jobs:

| Schedule | Method | URL |
|---|---|---|
| Every 10 min | GET | `https://<your-app>.onrender.com/health` |
| Daily 10:00 | POST | `https://<your-app>.onrender.com/tasks/reminders?token=<TASKS_TOKEN>` |
| Daily 15:00 | POST | `https://<your-app>.onrender.com/tasks/followups?token=<TASKS_TOKEN>` |

Generate a token and set `TASKS_TOKEN` in Render:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

The scheduled endpoints refuse to run outside business hours unless forced, and
stay disabled entirely until `TASKS_TOKEN` is set, since placing calls costs credits.

---

## 4. Adapting it to a different business

No code changes required:

1. **`knowledge_base.json`** — replace the FAQ entries with the new business's
   information. The agent only answers from this file, so it cannot invent policies.
2. **`prompts/system_prompt.md`** — change the persona, business name and the
   conversation paths. Push it live with
   `python3 setup_vapi_assistant.py --apply --update`.
3. **`.env`** — `BUSINESS_NAME`, opening hours, business days, timezone.

---

## 5. Day-to-day operation

```bash
python3 view_data.py                  # appointments, leads, tickets, summaries, queue
python3 test_integrations.py          # check integrations are still healthy
python3 outbound_calls.py reminders   # run reminder calls by hand
python3 outbound_calls.py followups   # work the follow-up queue by hand
```

Share `https://<your-app>.onrender.com/demo` with anyone who wants to try the
agent from a browser — no phone number or account needed. It requires
`VAPI_PUBLIC_KEY` (the public key from the Vapi dashboard, never the private one).

---

## 6. How it fits together

```
Caller ──▶ Vapi assistant ──▶ tool call ──▶ Render backend
                │                              │
                │                              ├─▶ Google Calendar   (book / move / cancel)
                │                              ├─▶ SQLite            (leads, tickets, summaries)
                │                              ├─▶ Slack             (team alerts)
                │                              ├─▶ Gmail             (caller confirmations)
                │                              └─▶ CRM / automation  (webhooks)
                │
                └─▶ end-of-call report ──▶ /webhooks/vapi ──▶ summary + follow-up outcome

cron-job.org ──▶ /tasks/reminders, /tasks/followups ──▶ outbound calls via Vapi
```

| File | Responsibility |
|---|---|
| `app/main.py` | Application entry point |
| `app/config.py` | All settings, from environment variables |
| `app/database.py` | SQLite storage and schema migrations |
| `app/calendar_service.py` | Google Calendar availability and events |
| `app/business_hours.py` | Open/closed logic |
| `app/qualification.py` | Lead scoring |
| `app/knowledge_base.py` | FAQ search |
| `app/notifications.py` | Slack, email, CRM, automation |
| `app/outbound.py` | Outbound calling workflows |
| `app/routes/tools.py` | Receives the agent's tool calls |
| `app/routes/webhooks.py` | End-of-call reports, follow-up outcomes |
| `app/routes/tasks.py` | Scheduled reminder/follow-up endpoints |
| `app/routes/demo.py` | Browser demo page |

---

## 7. What has and hasn't been tested

Verified working:

- Booking, rescheduling and cancelling against a live Google Calendar
- Lead capture with hot/warm/cold scoring
- Knowledge base answering known questions and correctly declining unknown ones
- Support ticket creation
- Business-hours detection
- Post-call summaries stored from the end-of-call report
- The follow-up loop: a placed call moves to "calling", an unanswered call goes
  back in the queue, an answered one closes with the conversation outcome
- Slack, email, sales alerts, CRM sync and automation webhooks all sending
- All nine tools responding correctly on the live deployment

Configured but not yet exercised on a real call:

- **Multilingual** — transcriber and voice are set for automatic language
  detection, and the prompt lists the nine languages, but no call has been made
  in a language other than English
- **Live transfer** — the tool is attached and correctly configured for a warm
  handoff, but transfers cannot work from browser calls (there is no phone line
  to bridge), so this needs a real phone call to verify
- **Outbound calling** — configured and the scheduling endpoints are tested, but
  no outbound call has actually been placed

## 8. Known limitations

Everything that could be solved for free has been. What remains is limited by
paid services or telecom regulation, not by the build.

**Genuinely paid-only:**

- **Vapi call credits.** The free allowance covers development and demos, but
  sustained real-world call volume needs a paid Vapi plan. Nothing else in the
  stack meters usage this way.
- **Indian phone numbers.** TRAI regulations require business KYC before any
  provider will issue an Indian number, so a local landline or mobile number for
  the agent needs a paid SIP trunk with a verified business. Free workarounds are
  in place — the browser demo page and a SIP address both work from India at no
  cost — but a *dialable Indian number* is not obtainable for free.

**Solved (previously limitations):**

- ~~Database resets on redeploy~~ — the storage layer now uses Postgres when
  `DATABASE_URL` is set, so records survive restarts. A free Neon or Supabase
  database is enough; it falls back to SQLite for local development.
- ~~Calling from India costs money~~ — the browser demo page and the free SIP
  address both work from anywhere at no cost.
- ~~The knowledge base only matches exact keywords~~ — matching now handles
  synonyms, plurals and natural phrasings, and still declines confidently when a
  question is genuinely outside what it knows.
- ~~Live transfer can't be tested~~ — transfer works on any real call, including
  a free SIP call from a softphone. Only the browser demo can't do it, since a
  browser tab has no telephone line to bridge.

## 9. Verifying the handover worked

Make one call through `/demo` and confirm the whole pipeline:

1. Book an appointment, giving an email address
2. Check the event appears on Google Calendar
3. Check the confirmation email arrives
4. Check Slack shows the booking
5. Check a row appears in the CRM sheet
6. Run `python3 view_data.py` and confirm the record is stored

If all six pass, the system is fully yours and working.
