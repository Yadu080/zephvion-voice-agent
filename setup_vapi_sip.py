"""Create a free SIP address for the assistant, so you can call it from a
softphone over the internet — no phone number, no international charges.

Useful when testing from outside the US, where Vapi's free numbers live.

Usage:
    python3 setup_vapi_sip.py                 # create (or show) the SIP address
    python3 setup_vapi_sip.py --list          # list phone numbers on the account

Requires VAPI_API_KEY and VAPI_ASSISTANT_ID in .env.
"""

import json
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from app import config  # noqa: E402

API = "https://api.vapi.ai/phone-number"
SIP_HOST = "sip.vapi.ai"          # use sip.eu.vapi.ai for the EU region
SIP_USERNAME = "zephvion-agent"   # becomes sip:<this>@sip.vapi.ai

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


def list_numbers(api_key):
    numbers = _request("GET", API, api_key)
    return numbers if isinstance(numbers, list) else []


def main():
    api_key = config.vapi_api_key()
    assistant_id = config.vapi_assistant_id()

    if not api_key or not assistant_id:
        print("Set VAPI_API_KEY and VAPI_ASSISTANT_ID in .env first.")
        return

    try:
        numbers = list_numbers(api_key)
    except urllib.error.HTTPError as exc:
        print(f"Could not list phone numbers: HTTP {exc.code} {exc.read().decode('utf-8')[:200]}")
        return

    if "--list" in sys.argv:
        print(f"{len(numbers)} phone number(s) on this account:")
        for n in numbers:
            label = n.get("sipUri") or n.get("number") or "(no identifier)"
            print(f"  {label}   provider={n.get('provider')}   id={n.get('id')}")
        return

    sip_uri = f"sip:{SIP_USERNAME}@{SIP_HOST}"

    for n in numbers:
        if n.get("sipUri") == sip_uri:
            print(f"SIP address already exists: {sip_uri}")
            print(f"   (id: {n.get('id')})")
            _print_instructions(sip_uri)
            return

    try:
        created = _request("POST", API, api_key, {
            "provider": "vapi",
            "sipUri": sip_uri,
            "assistantId": assistant_id,
        })
        print(f"Created SIP address: {created.get('sipUri', sip_uri)}")
        print(f"   (id: {created.get('id')})")
        _print_instructions(sip_uri)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")[:400]
        print(f"Failed: HTTP {exc.code} {detail}")
        if exc.code == 400 and "sipUri" in detail:
            print(f"\nThe username '{SIP_USERNAME}' may already be taken globally. "
                  "Edit SIP_USERNAME at the top of this file and run again.")


def _print_instructions(sip_uri):
    print(f"""
How to call it from India (free, over the internet):

  1. Install a free SIP softphone:
       - Linphone   (iOS / Android / Mac / Windows) - fully free, open source
       - Zoiper     (iOS / Android / Mac / Windows) - free tier is enough
  2. Skip / cancel any "create an account" or "sign in" prompt — you do not
     need a SIP account, and no registration is required.
  3. Find the dial pad or address bar and dial exactly:

       {sip_uri}

  4. The assistant answers like a normal phone call.

No phone number, no international charges. Call minutes still use your
Vapi credits, the same as any other call.
""")


if __name__ == "__main__":
    main()
