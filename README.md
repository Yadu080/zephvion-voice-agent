# Zephvion AI Voice Agent

An AI voice agent that answers customer calls 24/7 — booking appointments on a
real calendar, answering questions, qualifying leads, raising support tickets,
escalating to humans, and making outbound follow-up calls.

Built to run entirely on free tiers.

---

## What it does

| Capability | How |
|---|---|
| Answers incoming calls | Conversational voice agent (Vapi) |
| Books / reschedules / cancels appointments | Live Google Calendar integration |
| Answers questions about the business | Curated knowledge base — no invented answers |
| Captures and qualifies leads | Scores each enquiry hot / warm / cold |
| Raises support tickets | With priority levels and a ticket number |
| Escalates to a human | Warm transfer, briefing the person on the conversation first |
| Works outside business hours | Detects open/closed and adapts |
| Summarises every call | Summary, transcript, duration and outcome |
| Notifies the team | Slack, email, CRM sync, automation webhooks |
| Calls customers back | Appointment reminders and follow-ups, on a schedule |
| Speaks nine languages | Detected automatically |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill it in
uvicorn app.main:app --port 8000
```

**Storage:** set `DATABASE_URL` to a Postgres connection string and records
persist across restarts — necessary on hosts with an ephemeral filesystem, such
as Render's free tier. Leave it blank and it uses a local SQLite file, so local
development needs no database server.

Full setup — Google Calendar, Vapi, deployment, notifications — is in
**[HANDOVER.md](HANDOVER.md)**.

## Everyday commands

```bash
python3 view_data.py                  # appointments, leads, tickets, summaries
python3 test_integrations.py --send   # verify Slack / email / CRM actually work
python3 outbound_calls.py reminders   # call tomorrow's appointments
python3 outbound_calls.py followups   # work the follow-up queue
```

## Provisioning scripts

These recreate the whole agent in any Vapi account, so the project isn't tied
to whoever set it up:

```bash
python3 setup_vapi_tools.py              # the 9 function tools
python3 setup_vapi_assistant.py --apply  # assistant, prompt, multilingual config
python3 setup_vapi_transfer.py +91XXXXXXXXXX   # human handoff destination
python3 setup_vapi_sip.py                # SIP address for testing
```

## Layout

```
app/
  main.py               Application entry point
  config.py             Settings, all from environment variables
  database.py           Storage (Postgres or SQLite) and schema migrations
  calendar_service.py   Google Calendar availability and events
  business_hours.py     Open/closed logic
  qualification.py      Lead scoring
  knowledge_base.py     FAQ search
  notifications.py      Slack, email, CRM, automation webhooks
  outbound.py           Outbound calling workflows
  routes/
    tools.py            Receives the agent's tool calls
    webhooks.py         End-of-call reports and follow-up outcomes
    tasks.py            Scheduled reminder / follow-up endpoints
    demo.py             Browser demo page
knowledge_base.json     The business's FAQ content
prompts/                The agent's instructions
docs/                   Setup guide, conversation design, CRM script
```

## Adapting it to another business

No code changes needed:

1. `knowledge_base.json` — the business's FAQs
2. `prompts/system_prompt.md` — persona and conversation paths
3. `.env` — name, opening hours, timezone

## Documentation

- **[HANDOVER.md](HANDOVER.md)** — taking ownership, step by step
- **[docs/setup-guide.md](docs/setup-guide.md)** — full setup and operations
- **[docs/conversation_flow.md](docs/conversation_flow.md)** — how calls are designed to go
- **[docs/google-sheets-crm.gs](docs/google-sheets-crm.gs)** — free CRM webhook
