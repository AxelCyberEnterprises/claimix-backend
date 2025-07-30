"""
triage_runner.py   (formerly run_triage.py)
───────────────────────────────────────────────────────────────────────────────
Invokes the dedicated “Triage” assistant to identify incident types and an
incident description based on the running conversation context.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from utils import get_session_folder, load_json, save_json, get_claim_file

# ────────────────────────────────────────────────────────────────────────────
# Environment / OpenAI client
# ────────────────────────────────────────────────────────────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TRIAGE_ASSISTANT_ID: str | None = os.getenv("TRIAGE_ASSISTANT_ID")


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def run_triage(email: str, conversation_context: Any) -> Dict[str, Any]:
    """
    Call the triage assistant, persist its findings into <session>/claim.json
    and return the updated claim dict.

    Parameters
    ----------
    email : str
        Claimant’s e-mail address.
    conversation_context : Any
        The conversation history (whatever format the orchestrator maintains).

    Raises
    ------
    RuntimeError
        If the assistant fails or does not return the expected parameters.
    """
    if not TRIAGE_ASSISTANT_ID:
        raise RuntimeError("TRIAGE_ASSISTANT_ID env variable is not set.")

    # Single user block that contains the conversation in JSON
    user_content = [{
        "type": "text",
        "text": json.dumps({"conversation_context": conversation_context})
    }]

    # 1) create thread & enqueue assistant
    thread = client.beta.threads.create(messages=[{
        "role": "user",
        "content": user_content
    }])

    run_obj = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=TRIAGE_ASSISTANT_ID
    )

    # 2) poll until finished
    while run_obj.status not in {"completed", "failed"}:
        time.sleep(1)
        run_obj = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run_obj.id
        )

    if run_obj.status != "completed":
        raise RuntimeError(f"Triage run failed: {run_obj.status}")

    # 3) fetch latest assistant message (descending order = latest first)
    messages = client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=1)
    if not messages.data:
        raise RuntimeError("Triage assistant did not return any message.")

    last_msg = messages.data[0]
    text_block = last_msg.content[0].text
    response_text = text_block.value if hasattr(text_block, "value") else str(text_block)

    try:
        parsed = json.loads(response_text)
        incident_types = parsed["parameters"]["incident_type"]
        incident_description = parsed["parameters"]["incident_description"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("Triage assistant did not return the expected JSON.") from exc

    # 4) save into claim.json
    claim_path = get_claim_file(email)
    claim_data = load_json(claim_path, default={})
    claim_data.update({
        "incident_types": incident_types,
        "incident_description": incident_description,
        "stage": "TRIAGED"
    })
    save_json(claim_path, claim_data)

    return claim_data


# ────────────────────────────────────────────────────────────────────────────
# Manual test helper
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    import sys, pprint
    if len(sys.argv) != 3:
        print("usage: triage_runner.py <email> <conversation-json-string>")
        raise SystemExit(1)

    pprint.pprint(
        run_triage(sys.argv[1], json.loads(sys.argv[2])),
        width=100, compact=True
    )