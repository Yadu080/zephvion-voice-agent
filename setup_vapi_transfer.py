"""Create the Transfer Call tool and attach it to the assistant.

Uses a *warm* transfer: before connecting, the agent speaks a short summary of
the conversation to the person receiving the call. That satisfies the spec's
"Transfer to the Appropriate Team Member -> Provide Conversation Context" —
a blind transfer would hand over a caller with no context at all.

Usage:
    python3 setup_vapi_transfer.py                      # uses ESCALATION_PHONE_NUMBER from .env
    python3 setup_vapi_transfer.py +919876543210        # or pass the number directly

Requires VAPI_API_KEY and VAPI_ASSISTANT_ID in .env.
"""

import json
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from app import config  # noqa: E402

TOOL_API = "https://api.vapi.ai/tool"
ASSISTANT_API = "https://api.vapi.ai/assistant"

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


def build_tool(number):
    return {
        "type": "transferCall",
        "destinations": [
            {
                "type": "number",
                "number": number,
                "description": (
                    "Transfer here when the caller asks to speak to a human, or when the "
                    "request is beyond what the assistant can handle."
                ),
                "message": "Let me connect you with a team member now, one moment.",
                "transferPlan": {
                    "mode": "warm-transfer-say-summary",
                    "summaryPlan": {
                        "enabled": True,
                        "timeoutSeconds": 5,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Summarize in two sentences who is calling and what "
                                    "they need, so the person taking over has context. "
                                    "Return only the summary."
                                ),
                            },
                            {"role": "user", "content": "{{transcript}}"},
                        ],
                    },
                },
            }
        ],
    }


def main():
    api_key = config.vapi_api_key()
    assistant_id = config.vapi_assistant_id()
    number = sys.argv[1] if len(sys.argv) > 1 else config.escalation_phone_number()

    if not api_key or not assistant_id:
        print("Set VAPI_API_KEY and VAPI_ASSISTANT_ID in .env first.")
        return

    if not number:
        print("No destination number given.\n")
        print("Either pass it directly:")
        print("    python3 setup_vapi_transfer.py +919876543210")
        print("or set ESCALATION_PHONE_NUMBER in .env.\n")
        print("Use full international format, e.g. +91 for India.")
        return

    if not number.startswith("+"):
        print(f"'{number}' should be in international format, starting with + "
              "(e.g. +919876543210).")
        return

    try:
        tools = _request("GET", TOOL_API, api_key)
        existing = next((t for t in tools if t.get("type") == "transferCall"), None)

        if existing:
            tool = _request("PATCH", f"{TOOL_API}/{existing['id']}", api_key, build_tool(number))
            tool_id = existing["id"]
            print(f"Updated existing transfer tool -> {number}")
        else:
            tool = _request("POST", TOOL_API, api_key, build_tool(number))
            tool_id = tool.get("id")
            print(f"Created transfer tool -> {number}")

        # Attach it to the assistant alongside the existing tools.
        assistant = _request("GET", f"{ASSISTANT_API}/{assistant_id}", api_key)
        model = assistant.get("model") or {}
        tool_ids = list(model.get("toolIds") or [])

        if tool_id in tool_ids:
            print("Already attached to the assistant.")
        else:
            tool_ids.append(tool_id)
            _request("PATCH", f"{ASSISTANT_API}/{assistant_id}", api_key,
                     {"model": {**model, "toolIds": tool_ids}})
            print(f"Attached to the assistant ({len(tool_ids)} tools total).")

        print("\nWarm transfer is on: the agent will summarise the conversation to "
              "whoever answers before connecting the caller.")
    except urllib.error.HTTPError as exc:
        print(f"Failed: HTTP {exc.code} {exc.read().decode('utf-8')[:400]}")


if __name__ == "__main__":
    main()
