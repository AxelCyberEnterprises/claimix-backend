"""
clarifying_question.py
───────────────────────────────────────────────────────────────────────────────
Creates a single, open-ended clarifying question based on the claimant’s first
message and any attachment OCR data.  The question is e-mailed to the claimant
and the JSON result is returned to the caller.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Any

from dotenv import load_dotenv
from openai import OpenAI

from .utils import (
    ensure_session_structure,
    load_json,
    save_json,
)
from .db_helper import get_claim_context
from .email_utils import send_email  # e-mail helper

# ────────────────────────────────────────────────────────────────────────────
# Environment / OpenAI client
# ────────────────────────────────────────────────────────────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ────────────────────────────────────────────────────────────────────────────
# JSON schema and prompt
# ────────────────────────────────────────────────────────────────────────────
CLARIFY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "clarifying_question": {
            "type": "string",
            "description": "A single open-ended question asking for the most critical missing context.",
        }
    },
    "required": ["clarifying_question"],
    "additionalProperties": False,
}

CLARIFY_INSTRUCTION: str = """
You are the Clarifying Question Assistant for an automotive-insurance claim
system.  After reading the user’s initial description and any attachment
information, generate ONE well-structured, open-ended question that gathers the
most critical missing context.

Do NOT classify the incident; simply infer likely incident categories and ask
the question accordingly.

– Always include sub-questions, if needed, in a natural flowing manner.
– Always ask about territorial usage, general exceptions, vehicle security and
  administrative matters.

Return exactly one JSON object that matches the provided schema.
"""

# ────────────────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────────────────


def _load_attachment_summary(session_folder: str) -> str:
    """
    Read `<session>/attachment_data.json` (if any) and build a plain-text
    summary suitable for the language model prompt.
    """
    ad_path = os.path.join(session_folder, "attachment_data.json")
    if not os.path.exists(ad_path):
        return ""

    data = load_json(ad_path, default={})
    details: List[Dict[str, str]] = data.get("attachment_details", [])
    parts: List[str] = []
    for att in details:
        name, det = att.get("name", "unknown"), att.get("details", "")
        if det:
            parts.append(f"[{name}]\n{det}")
    return "\n\n".join(parts)


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def run_clarifying_question(claim_id: str, message_text: str) -> Dict[str, str]:
    """
    Build the clarifying question, e-mail it to the claimant and return the
    parsed JSON response.
    
    Args:
        claim_id: The unique claim ID
        message_text: The message text to analyze
    """
    # Get the claim to access the sender's email
    claim = get_claim_context(claim_id)
    if not claim:
        print(f"[CLARIFICATION] Error: Claim {claim_id} not found")
        return {"error": "Claim not found"}
        
    sender_email = claim.get('sender_email')
    if not sender_email:
        print(f"[CLARIFICATION] Error: No sender email found for claim {claim_id}")
        return {"error": "No sender email found"}
        
    session_folder: str = ensure_session_structure(claim_id)

    # user blocks for the LLM (initial message + attachment summary)
    user_blocks: List[Dict[str, Any]] = [{"type": "input_text", "text": message_text}]
    attachment_summary = _load_attachment_summary(session_folder)
    if attachment_summary:
        user_blocks.append(
            {"type": "input_text", "text": "Attachment Details:\n" + attachment_summary}
        )

    # OpenAI call
    response = client.responses.create(
        model="gpt-4.1",
        input=[
            {"role": "system", "content": CLARIFY_INSTRUCTION},
            {"role": "user", "content": user_blocks},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "CLARIFY_INCIDENT",
                "schema": CLARIFY_SCHEMA,
                "strict": True,
            }
        },
    )

    result: Dict[str, str] = json.loads(response.output_text)

    # E-mail the question
    subject = "Quick clarification needed to process your claim"
    html_body = (
        f"<p>Dear Valued Customer,</p>"
        f"<p>Thank you for submitting your claim (Reference: {claim_id}).</p>"
        "<p>To help us process your claim more efficiently, we need a bit more information:</p>"
        f"<p style='background-color: #f5f5f5; padding: 15px; border-left: 4px solid #4a90e2;'>"
        f"<b>{result['clarifying_question']}</b>"
        "</p>"
        "<p>Please reply to this email with the requested information at your earliest convenience.</p>"
        "<p>Best regards,<br>Axel Claims Team</p>"
    )
    print(f"[CLARIFICATION] Sending email to {sender_email} for claim {claim_id}")
    send_email(to=sender_email, subject=subject, html=html_body)

    # Persist for reference (optional)
    save_json(os.path.join(session_folder, "clarifying_question.json"), result)

    return result


# ────────────────────────────────────────────────────────────────────────────
# Manual test
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    import sys, pprint

    if len(sys.argv) < 3:
        print("usage: clarifying_question.py <email> <message text>")
        raise SystemExit(1)

    pprint.pprint(
        run_clarifying_question(sys.argv[1], " ".join(sys.argv[2:])),
        width=100,
        compact=True,
    )