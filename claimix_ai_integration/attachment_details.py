
from __future__ import annotations

import base64
import json
import os
from typing import Dict, List

from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path

from .document_processor import process_and_update_claim_session
from .utils import (
    SUPPORTED_IMAGE_EXTENSIONS,
    PDF_EXT,
    ensure_claim_session_structure_by_id,
    save_json,
)

# ────────────────────────────────────────────────────────────────────────────
# OpenAI set-up
# ────────────────────────────────────────────────────────────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ATTACHMENT_DETAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "attachment_details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "details": {"type": "string"},
                },
                "required": ["name", "details"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["attachment_details"],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTION = (
    "You are the Attachment Details Assistant.\n"
    "For each attachment, combine any provided OCR / extracted text and the "
    "visual content to craft a concise, vivid description. Return exactly one "
    "JSON object that matches the schema."
)

# ────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ────────────────────────────────────────────────────────────────────────────
def _encode_image(path: str) -> str:
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _pdf_page_image_blocks(pdf_path: str) -> List[Dict]:
    blocks: List[Dict] = []
    for page_index, page in enumerate(convert_from_path(pdf_path, dpi=200)):
        tmp_jpg = f"{pdf_path}_page_{page_index}.jpg"
        page.save(tmp_jpg, "JPEG")
        blocks.append({"type": "input_image", "image_url": _encode_image(tmp_jpg)})
        os.remove(tmp_jpg)
    return blocks


def _build_image_blocks(session_folder: str, attachments: List[str]) -> List[Dict]:
    """
    Image blocks for:
      • original photos
      • rendered PDF pages
    (DOCX/DOC/TXT are *not* rendered; their text is sent only as text blocks.)
    """
    blocks: List[Dict] = []
    for fname in attachments:
        fpath = os.path.join(session_folder, "attachments", fname)
        if not os.path.exists(fpath):
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            blocks.append({"type": "input_image", "image_url": _encode_image(fpath)})
        elif ext == PDF_EXT:
            blocks.extend(_pdf_page_image_blocks(fpath))

    return blocks


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def generate_attachment_details(claim_id: str, attachments: List[str]) -> Dict:
    """
    1. Runs extraction (document_processor)
    2. Builds text + image blocks per latest rules
    3. Calls OpenAI Responses API
    4. Saves attachment_data.json and returns the parsed result.
    """
    session_folder = ensure_claim_session_structure_by_id(claim_id)
    parsed_docs = process_and_update_claim_session(claim_id)

    user_blocks: List[Dict] = []

    # text blocks (PDF OCR, DOCX/DOC/TXT extraction)
    for fname in attachments:
        text = (parsed_docs.get(fname) or {}).get("text", "")
        if text.strip():
            user_blocks.append(
                {"type": "input_text", "text": f"{fname} OCR:\n{text.strip()[:1000]}"}
            )

    # image blocks (photos + PDF pages)
    user_blocks.extend(_build_image_blocks(session_folder, attachments))

    response = client.responses.create(
        model="gpt-4.1",
        input=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_blocks},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "ATTACHMENT_DETAILS",
                "schema": ATTACHMENT_DETAILS_SCHEMA,
                "strict": True,
            }
        },
    )

    result = json.loads(response.output_text)
    save_json(os.path.join(session_folder, "attachment_data.json"), result)
    return result
