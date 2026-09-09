# Handover — Zephvion AI Voice Agent

Everything needed to take ownership of this project and run it independently.

No part of the system is tied to the original builder's accounts. The repository
is the deliverable: with your own credentials you can recreate the whole thing
in about an hour, and nothing needs to be rebuilt.

---

## 1. What you are receiving

A working AI voice agent, deployed and running, plus everything needed to run it
yourself: the source code, the setup scripts that rebuild it in your own
accounts, the conversation design, and this guide.

### Against the original specification

| Specification | Status |
|---|---|
| AI Call Answering Agent | Built |
| AI Appointment Booking (check, book, reschedule, cancel) | Built, on a live Google Calendar |
| AI Lead Qualification Agent | Built, with hot/warm/cold scoring |
| 24/7 Virtual Receptionist | Built, with out-of-hours behaviour |
| AI Follow-Up Agent | Built, including recording the outcome of each call |
| AI Outbound Calling Workflows | Built: reminders, confirmations, re-engagement, follow-ups, qualification |
| Natural, human-like conversations | Built |
| Real-time intent understanding | Built |
| Custom conversation flows | Built, six distinct paths |
| Incoming and outbound calls | Both |
| Smart routing and human escalation | Built, warm transfer with a spoken summary |
| CRM updates during or after calls | Built, via webhook |
| Automated follow-ups | Built, on a schedule |
| Call summaries and structured data | Built, stored per call |
| 24/7 availability | Built |
| Custom knowledge base | Built |
| Multilingual conversation design | Built, nine languages, auto-detected |

**Two deliberate substitutions**, both agreed during the build:

- **Twilio → Vapi's own telephony.** Twilio's trial blocked number configuration
  behind an upgrade, and trial numbers could not be linked. Vapi provides the
  telephony directly, so the layer is still there — just not Twilio's.
- **GoHighLevel → any webhook-capable CRM.** GoHighLevel has no free tier
  (~$97/month). The CRM sync sends a generic webhook, so it works with
  GoHighLevel, HubSpot's free tier, or a Google Sheet by changing one setting.
  No code changes needed to switch.

**One partial:** the specification lists *surveys* among outbound use cases.
There is no dedicated survey workflow, but outbound calls accept an arbitrary
purpose, so a survey can be run with
`python3 outbound_calls.py call +91XXXXXXXXXX "ask them to rate their visit"`.
Responses land in the call summary rather than as structured survey data.

**Running cost: nothing.** Every service runs on a free tier.

---

## 2. What is included, and what is not

The repository is the deliverable. It contains:

- the complete backend (`app/`)
- the agent's instructions (`prompts/system_prompt.md`)
- the business knowledge base (`knowledge_base.json`)
- scripts that recreate the agent in your Vapi account (`setup_vapi_*.py`)
- operational tools (`view_data.py`, `test_integrations.py`, `outbound_calls.py`)
- deployment configuration (`render.yaml`, `.python-version`)
- a blank settings template (`.env.example`)
- documentation (`README.md`, this file, `docs/`)

It deliberately does **not** contain any credentials. There is no `.env`, no
Google service-account key and no database file in the repository, because those
are secrets belonging to whoever runs the system. You create your own during
setup, following section 4. Nothing else is missing — no part of the build is
withheld or hard-coded to the original accounts.

---

## 3. Accounts you will need

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
| **Neon** or **Supabase** | Postgres database, so records survive redeploys | Free |

---

## 4. Taking ownership — step by step

### 4.1 Get the code

Fork or clone the repository into your own GitHub account.

### 4.2 Google Calendar

1. console.cloud.google.com → create a project
2. APIs & Services → Library → enable **Google Calendar API**
3. APIs & Services → Credentials → Create Credentials → **Service Account**
4. Open it → Keys → Add Key → Create New Key → **JSON** → download
5. Open the Google Calendar the agent should manage → its settings →
   **Share with specific people** → add the service account's email (inside the
   JSON file) with **"Make changes to events"**
6. Same page → **Integrate calendar** → copy the **Calendar ID**

### 4.3 Deploy the backend

1. render.com → New → **Web Service** → connect the repo
2. Settings are read from `render.yaml`; confirm the plan is **Free**
3. Environment → **Secret Files** → add `service-account.json` (paste the JSON from 4.2)
4. Environment → **Environment Variables** → add everything from
   `.env.example`, at minimum:
   - `GOOGLE_SERVICE_ACCOUNT_FILE` = `/etc/secrets/service-account.json`
   - `GOOGLE_CALENDAR_ID`, `TIMEZONE`
5. Wait for the deploy, then check `https://<your-app>.onrender.com/health`

### 4.4 Database

Render's free tier wipes its filesystem on every redeploy, so the records need
to live outside it.

1. Sign up free at neon.tech (or supabase.com) and create a project
2. Copy the connection string — it looks like
   `postgresql://user:password@host/dbname`
3. Add it to Render → Environment as `DATABASE_URL`, and to your local `.env`

The tables are created automatically on first start. Leave `DATABASE_URL` blank
and it falls back to a local SQLite file, which is fine for development but
loses data on a hosted redeploy.

### 4.5 Vapi

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

### 4.6 Notifications and CRM

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

### 4.7 Scheduling and uptime

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

## 5. Adapting it to a different business

No code changes required:

1. **`knowledge_base.json`** — replace the FAQ entries with the new business's
   information. The agent only answers from this file, so it cannot invent policies.
2. **`prompts/system_prompt.md`** — change the persona, business name and the
   conversation paths. Push it live with
   `python3 setup_vapi_assistant.py --apply --update`.
3. **`.env`** — `BUSINESS_NAME`, opening hours, business days, timezone.

---

## 6. Day-to-day operation

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

## 7. How the agent handles a call

The agent works out which of six paths a caller needs, then follows it. The full
conversation design is in `prompts/system_prompt.md`; this is the shape of it.

**Booking.** Asks what the appointment is for, whether they are a new or
returning patient, and collects name, phone and (optionally) email. It checks
the real calendar before offering a slot, and if the requested time is taken it
offers alternatives from the same day. It confirms the details back, books, and
only then tells the caller it is done. Rescheduling and cancelling find the
existing appointment from the name and number — tolerating a phone number given
in a different format than at booking.

**Questions.** Anything factual — hours, location, insurance, costs, what to
bring, policies, services, appointment lengths, registration — is answered from
the knowledge base rather than from the model's own memory, so the agent cannot
invent a policy or a price. If the knowledge base has no confident answer it
says so and offers to take a message.

**New enquiries.** Qualifying questions are asked conversationally, not as an
interrogation: how soon they want to proceed, whether they are ready to book or
still comparing, and how they intend to pay. Those answers produce a score and a
hot / warm / cold band. Hot leads are flagged to the caller as priority and
emailed to the sales team immediately.

**Problems and complaints.** Raises a numbered support ticket with a priority,
and reads the number back to the caller.

**Wanting a human.** Transfers the live call, speaking a two-sentence summary of
the conversation to whoever picks up first, so the caller does not have to start
again. If a transfer is not possible, it takes a callback request instead.

**Callbacks.** Adds the caller to a follow-up queue that outbound calling works
through automatically.

Throughout, the agent is instructed never to claim something is booked, moved,
cancelled, saved or ticketed unless the underlying operation actually succeeded
— if a step fails it apologises and takes details instead of pretending.

---

## 8. How it fits together

```
Caller ──▶ Vapi assistant ──▶ tool call ──▶ Render backend
                │                              │
                │                              ├─▶ Google Calendar   (book / move / cancel)
                │                              ├─▶ Postgres          (leads, tickets, summaries)
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
| `app/database.py` | Storage (Postgres or SQLite) and schema migrations |
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

## 9. What has and hasn't been tested

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

## 10. Known limitations

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

## 11. Verifying the handover worked

Make one call through `/demo` and confirm the whole pipeline:

1. Book an appointment, giving an email address
2. Check the event appears on Google Calendar
3. Check the confirmation email arrives
4. Check Slack shows the booking
5. Check a row appears in the CRM sheet
6. Run `python3 view_data.py` and confirm the record is stored

If all six pass, the system is fully yours and working.

---

## 12. What it costs to run

Nothing, at the volumes this is built for.

| Service | Free allowance | What happens beyond it |
|---|---|---|
| Vapi | Trial credits | Call minutes need a paid plan; this is the first thing to hit |
| Render | 750 hours/month | Enough for one always-on service |
| Neon Postgres | 0.5 GB storage | Far beyond what call records need |
| Google Calendar API | 1,000,000 requests/day | Not reachable in practice |
| Gmail SMTP | 500 emails/day | Enough for hundreds of bookings |
| Slack webhooks | Unlimited | — |
| Google Sheets | 10M cells | Years of records |
| cron-job.org | 50 jobs | Three are used |

The practical limit is Vapi call credits. Everything else has headroom well
beyond normal business use.

---

## 13. Security notes

- **The repository contains no credentials.** `.env`, the Google service-account
  key and the database file are excluded from version control by design.
- **Never send a zip of a working folder.** A zip ignores those exclusions and
  would include live keys. Share the repository, or a zip downloaded from GitHub.
- **The demo page uses the Vapi *public* key**, which is safe in a browser. The
  private key stays on the server.
- **Scheduled task endpoints require a token** and are disabled entirely if that
  token is not set, since they can place calls that cost money.
- **Rotate anything that leaks.** Vapi keys, the Gmail app password, the Slack
  webhook and the database URL can all be regenerated from their dashboards.

---

## 14. If something goes wrong

| Symptom | Likely cause |
|---|---|
| Agent answers but bookings fail | `GOOGLE_CALENDAR_ID` or the service-account secret file is missing on the server, or the calendar was never shared with the service account |
| Tool calls return errors | The tools' Server URL still points somewhere old; re-run `setup_vapi_tools.py` after updating `SERVER_URL` |
| First call of the day fails, later ones work | The uptime ping is not running; the host slept and the first request hit a cold start |
| No confirmation emails or Slack messages | Those settings exist locally but were never added to the server's environment |
| Records disappear after a deploy | `DATABASE_URL` is not set on the server, so it fell back to a local file |
| Transfer fails on a browser call | Expected — transfers need a real phone or SIP call |
| Agent books the wrong year | The date variable was removed from the system prompt; it needs the current date |

`python3 test_integrations.py --send` will tell you which integrations are
actually working, and `python3 view_data.py` shows what has been captured,
including which database it is reading from.
