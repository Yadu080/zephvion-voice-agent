"""Provision the whole assistant into a Vapi account from this repo.

This is what makes the project handover-able: anyone with their own Vapi
account can recreate the entire agent from source, with no access to
whoever built it.

Usage:
    python3 setup_vapi_assistant.py                 # show what would be created
    python3 setup_vapi_assistant.py --apply         # create a NEW assistant
    python3 setup_vapi_assistant.py --apply --update  # update VAPI_ASSISTANT_ID

By default this only prints the plan, so it can't clobber an assistant that
was tuned in the dashboard. Run setup_vapi_tools.py first so the tools exist.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app import config  # noqa: E402

ASSISTANT_API = "https://api.vapi.ai/assistant"
TOOL_API = "https://api.vapi.ai/tool"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"
SERVER_URL = "https://zephvion-voice-agent.onrender.com/webhooks/vapi"

ASSISTANT_NAME = "Riley — Wellness Partners Receptionist"
FIRST_MESSAGE = ("Thank you for calling Wellness Partners. This is Riley, "
                 "your scheduling assistant. How may I help you today?")

# "multilingual-auto" matches the voice to whatever language the caller speaks.
# For a fixed Indian-English voice instead, set VOICE_ID=en-IN-NeerjaNeural
# (or en-IN-PrabhatNeural) — but that stops the voice switching per language.
VOICE_PROVIDER = os.environ.get("VOICE_PROVIDER", "azure")
VOICE_ID = os.environ.get("VOICE_ID", "multilingual-auto")
DEFAULT_MODEL = os.environ.get("VAPI_MODEL", "gpt-4.1")

# Tools this assistant should have attached, by function name.
TOOL_NAMES = [
    "check_availability", "book_appointment", "reschedule_appointment",
    "cancel_appointment", "capture_lead", "answer_question",
    "create_support_ticket", "check_business_hours", "schedule_followup",
]

HEADERS_EXTRA = {
    "Accept": "application/json",
    # Cloudflare fronts api.vapi.ai and rejects urllib's default User-Agent.
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


def _request(method, url, api_key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(HEADERS_EXTRA)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def load_system_prompt() -> str:
    """The file has setup instructions above a '---' divider; the prompt itself
    is everything after it."""
    text = PROMPT_PATH.read_text()
    marker = "\n---\n"
    return (text.split(marker, 1)[1] if marker in text else text).strip()


def resolve_tool_ids(api_key):
    tools = _request("GET", TOOL_API, api_key)
    by_name = {}
    for tool in tools if isinstance(tools, list) else []:
        name = (tool.get("function") or {}).get("name")
        if name:
            by_name[name] = tool["id"]

    ids, missing = [], []
    for name in TOOL_NAMES:
        if name in by_name:
            ids.append(by_name[name])
        else:
            missing.append(name)
    return ids, missing


def existing_tool_ids(api_key, assistant_id):
    """Tool IDs already on the assistant — so an update doesn't drop tools that
    were added in the dashboard (e.g. a Transfer Call tool)."""
    if not assistant_id:
        return []
    try:
        assistant = _request("GET", f"{ASSISTANT_API}/{assistant_id}", api_key)
    except Exception as exc:
        print(f"[warning] Could not read existing assistant ({exc}); "
              "its dashboard-added tools may be dropped.")
        return []
    return (assistant.get("model") or {}).get("toolIds") or []


def multilingual_voice(current_voice):
    """Keep whatever voice is already chosen, but let it speak other languages.

    Vapi's own voices support automatic language selection via version 2, so a
    deliberately-chosen voice (e.g. an Indian one) isn't thrown away just to
    enable multilingual.
    """
    provider = (current_voice or {}).get("provider")
    voice_id = (current_voice or {}).get("voiceId")

    if provider == "vapi" and voice_id:
        return {"provider": "vapi", "voiceId": voice_id, "version": 2, "language": "auto"}
    if provider and voice_id:
        # Other providers: keep the voice as-is rather than silently swapping it.
        return {"provider": provider, "voiceId": voice_id}
    return {"provider": VOICE_PROVIDER, "voiceId": VOICE_ID}


def build_payload(system_prompt, tool_ids, current=None):
    """Change only what needs changing; carry everything else forward."""
    current = current or {}
    current_model = current.get("model") or {}

    payload = {
        "firstMessage": current.get("firstMessage") or FIRST_MESSAGE,
        "model": {
            "provider": current_model.get("provider", "openai"),
            "model": current_model.get("model", DEFAULT_MODEL),
            "messages": [{"role": "system", "content": system_prompt}],
            "toolIds": tool_ids,
        },
        # Deepgram with language "multi" detects the caller's language
        # automatically instead of assuming English.
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
        },
        "voice": multilingual_voice(current.get("voice")),
    }

    if not current:
        payload["name"] = ASSISTANT_NAME

    # Keep existing server config; only ensure end-of-call-report is included.
    server_url = (current.get("server") or {}).get("url") or SERVER_URL
    payload["server"] = {"url": server_url}

    messages = list(current.get("serverMessages") or [])
    if "end-of-call-report" not in messages:
        messages.append("end-of-call-report")
    payload["serverMessages"] = messages or ["end-of-call-report"]

    return payload


def main():
    api_key = config.vapi_api_key()
    if not api_key:
        print("Set VAPI_API_KEY in .env first.")
        return

    apply_changes = "--apply" in sys.argv
    update_existing = "--update" in sys.argv
    assistant_id = config.vapi_assistant_id()

    try:
        tool_ids, missing = resolve_tool_ids(api_key)
    except urllib.error.HTTPError as exc:
        print(f"Could not list tools: HTTP {exc.code} {exc.read().decode('utf-8')[:200]}")
        return

    if missing:
        print(f"Missing {len(missing)} tool(s): {', '.join(missing)}")
        print("Run:  python3 setup_vapi_tools.py\n")
        if apply_changes:
            return

    current = {}
    preserved = []
    if update_existing and assistant_id:
        try:
            current = _request("GET", f"{ASSISTANT_API}/{assistant_id}", api_key)
        except Exception as exc:
            print(f"[warning] Could not read the existing assistant ({exc}).")
        # Keep anything already attached in the dashboard (e.g. Transfer Call).
        preserved = [tid for tid in ((current.get("model") or {}).get("toolIds") or [])
                     if tid not in tool_ids]
        tool_ids = tool_ids + preserved

    system_prompt = load_system_prompt()
    payload = build_payload(system_prompt, tool_ids, current)

    model = payload["model"]
    voice = payload["voice"]
    print(f"Assistant      : {current.get('name') or ASSISTANT_NAME}")
    print(f"Model          : {model['provider']} {model['model']}"
          + (" (kept)" if current else " (default)"))
    print(f"Tools attached : {len(tool_ids)} "
          f"({len(TOOL_NAMES)} from this repo"
          + (f" + {len(preserved)} kept from the dashboard" if preserved else "")
          + ")")
    print(f"Transcriber    : deepgram nova-2, language=multi  [CHANGED for multilingual]")
    print(f"Voice          : {voice['provider']} {voice['voiceId']}"
          + (" version=2 language=auto  [multilingual enabled, voice kept]"
             if voice.get("language") == "auto" else ""))
    print(f"Server URL     : {payload['server']['url']}")
    print(f"Server messages: {len(payload['serverMessages'])} kept, incl. end-of-call-report")
    print(f"System prompt  : {len(system_prompt)} characters  [CHANGED]")

    if not apply_changes:
        print("\nDry run — nothing was changed.")
        print("  Create a new assistant:      python3 setup_vapi_assistant.py --apply")
        print("  Update the one in .env:      python3 setup_vapi_assistant.py --apply --update")
        return

    try:
        if update_existing:
            if not assistant_id:
                print("VAPI_ASSISTANT_ID is not set in .env — nothing to update.")
                return
            result = _request("PATCH", f"{ASSISTANT_API}/{assistant_id}", api_key, payload)
            print(f"\nUpdated assistant {assistant_id}")
        else:
            result = _request("POST", ASSISTANT_API, api_key, payload)
            new_id = result.get("id")
            print(f"\nCreated assistant {new_id}")
            print(f"Add this to your .env:\n  VAPI_ASSISTANT_ID={new_id}")

        print("\nStill to do in the dashboard:")
        print("  - Pick a voice (Azure en-IN-NeerjaNeural works well, no extra account)")
        print("  - Attach a phone number or SIP address to the assistant")
        print("  - Add a Transfer Call tool if you want live human handoff")
    except urllib.error.HTTPError as exc:
        print(f"Failed: HTTP {exc.code} {exc.read().decode('utf-8')[:400]}")


if __name__ == "__main__":
    main()
