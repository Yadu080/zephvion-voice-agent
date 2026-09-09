"""A shareable click-to-talk demo page.

Anyone with the link can speak to the agent from a browser — no phone number,
no app, no account, and no international call charges. Useful for demoing and
for testing from outside the US, where the free Vapi number lives.

Needs VAPI_PUBLIC_KEY (the *public* key from the Vapi dashboard — never the
private one, since this runs in the visitor's browser).
"""

import html
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app import config

router = APIRouter()

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{business} — Talk to Riley</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0d1117; color: #e6edf3; padding: 24px;
  }}
  .card {{
    max-width: 560px; width: 100%; background: #161b22; border: 1px solid #30363d;
    border-radius: 16px; padding: 32px;
  }}
  h1 {{ margin: 0 0 4px; font-size: 24px; }}
  .sub {{ color: #8b949e; margin: 0 0 24px; }}
  .hint {{
    background: #0d1117; border: 1px solid #30363d; border-radius: 10px;
    padding: 16px 20px; margin: 24px 0 0;
  }}
  .hint p {{ margin: 0 0 8px; font-weight: 600; font-size: 14px; }}
  ul {{ margin: 0; padding-left: 20px; color: #8b949e; font-size: 14px; }}
  li {{ margin-bottom: 6px; }}
  .note {{ font-size: 13px; color: #8b949e; margin-top: 24px; }}
  .warn {{
    background: #2d1b17; border: 1px solid #6b3d2e; color: #ffa198;
    border-radius: 10px; padding: 16px 20px;
  }}
  code {{ background: #0d1117; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
</style>
</head>
<body>
  <div class="card">
    <h1>{business}</h1>
    <p class="sub">Talk to Riley, our AI receptionist — right from your browser.</p>

    {body}

    <div class="hint">
      <p>Things to try</p>
      <ul>
        <li>“I'd like to book an appointment with a therapist next Tuesday”</li>
        <li>“What are your opening hours?” or “Do you accept insurance?”</li>
        <li>“I need to reschedule my appointment” / “Cancel my appointment”</li>
        <li>“I want to speak to a human”</li>
        <li>Try it in Hindi, Kannada or Tamil — it should reply in the same language</li>
      </ul>
    </div>

    <p class="note">
      Click the call button (bottom-right), allow microphone access, and start
      talking. Works best in Chrome.
    </p>
  </div>
{script}
</body>
</html>
"""

WIDGET = """
<script>
  var vapiInstance = null;
  (function (d, t) {{
    var g = d.createElement(t), s = d.getElementsByTagName(t)[0];
    g.src = "https://cdn.jsdelivr.net/gh/VapiAI/html-script-tag@latest/dist/assets/index.js";
    g.defer = true; g.async = true;
    s.parentNode.insertBefore(g, s);
    g.onload = function () {{
      vapiInstance = window.vapiSDK.run({{
        apiKey: "{public_key}",
        assistant: "{assistant_id}",
        config: {{}}
      }});
    }};
  }})(document, "script");
</script>
"""

NOT_CONFIGURED = """
    <div class="warn">
      <strong>Not configured yet.</strong><br>
      Set <code>VAPI_PUBLIC_KEY</code> and <code>VAPI_ASSISTANT_ID</code> in the
      server environment. The public key is in the Vapi dashboard under API Keys —
      use the <em>public</em> key here, never the private one.
    </div>
"""


@router.get("/demo", response_class=HTMLResponse)
def demo_page():
    public_key = os.environ.get("VAPI_PUBLIC_KEY", "").strip()
    assistant_id = (config.vapi_assistant_id() or "").strip()

    if public_key and assistant_id:
        body = ('<p class="sub">Press the call button in the corner to start.</p>')
        script = WIDGET.format(
            public_key=html.escape(public_key, quote=True),
            assistant_id=html.escape(assistant_id, quote=True),
        )
    else:
        body = NOT_CONFIGURED
        script = ""

    return PAGE.format(
        business=html.escape(config.BUSINESS_NAME),
        body=body,
        script=script,
    )
