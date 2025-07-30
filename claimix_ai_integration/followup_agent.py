"""
followup_agent.py
───────────────────────────────────────────────────────────────────────────────
Aggregates open questions from specialist agents, deduplicates them via the
Follow-Up Assistant (OpenAI Responses API), e-mails the claimant a single
clarification e-mail, and returns the JSON response.

Public function
---------------
run_follow_up_agent(email: str) -> dict
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, List

from dotenv import load_dotenv
from openai import OpenAI

from utils import (
    ensure_session_structure,
    load_json,
    save_json,
)
from advanced_imap_listener import send_email  # STARTTLS-only mail helper

# ────────────────────────────────────────────────────────────────────────────
# Environment / OpenAI client
# ────────────────────────────────────────────────────────────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ────────────────────────────────────────────────────────────────────────────
# JSON schema and prompt
# ────────────────────────────────────────────────────────────────────────────
FOLLOW_UP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "email_html": {
            "type": "string",
            "description": "HTML-formatted list of deduplicated follow-up questions.",
        }
    },
    "required": ["email_html"],
    "additionalProperties": False,
}

FOLLOW_UP_INSTRUCTION: str = """
You are the Follow-Up Agent in an AI-powered automotive insurance claim system.

Given a JSON object that aggregates possible open questions from multiple
specialist agents, produce a single professional HTML e-mail body that starts
with:

<b>To help us proceed with your claim, please respond to the following questions:</b><br><br>

Then list each deduplicated, well-phrased question, numbered and separated by
<br> tags.

Return exactly one JSON object matching the provided schema – nothing else.
"""

# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def run_follow_up_agent(email: str) -> Dict[str, Any]:
    """
    1. Reads <session>/follow_up.json (must exist and contain 'responses')
    2. Calls the OpenAI Follow-Up Assistant
    3. Saves the HTML to <session>/follow_up_email.json
    4. Sends the e-mail to the claimant
    5. Removes follow_up.json (processed)
    6. Returns the parsed JSON result
    """
    session_folder: str = ensure_session_structure(email)
    follow_up_input = os.path.join(session_folder, "follow_up.json")

    if not os.path.exists(follow_up_input):
        raise FileNotFoundError("follow_up.json not found for session.")

    payload = load_json(follow_up_input, default={})
    specialist_outputs: List[Dict[str, Any]] = payload.get("responses", [])
    if not specialist_outputs:
        raise ValueError("No 'responses' found in follow_up.json.")

    # ---------------- OpenAI call ----------------
    response = client.responses.create(
        model="gpt-4.1",
        input=[
            {"role": "system", "content": FOLLOW_UP_INSTRUCTION},
            {"role": "user", "content": json.dumps({"specialist_outputs": specialist_outputs})},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "FOLLOW_UP_EMAIL",
                "schema": FOLLOW_UP_SCHEMA,
                "strict": True,
            }
        },
    )

    result: Dict[str, str] = json.loads(response.output_text)
    email_html: str = result["email_html"]

    # ---------------- Persist & e-mail ----------------
    email_path = os.path.join(session_folder, "follow_up_email.json")
    save_json(email_path, result)

    subject = "Further information required to process your claim"
    if not send_email(to=email, subject=subject, html=email_html):
        raise RuntimeError("Unable to send follow-up e-mail.")

    # ---------------- House-keeping ----------------
    os.remove(follow_up_input)  # mark as processed

    return result


# ────────────────────────────────────────────────────────────────────────────
# Manual test helper
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    import sys, pprint
    if len(sys.argv) != 2:
        print("usage: followup_agent.py <claimant-email>")
        raise SystemExit(1)

    pprint.pprint(run_follow_up_agent(sys.argv[1]), width=100, compact=True)