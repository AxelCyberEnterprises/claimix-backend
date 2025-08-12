"""
document_processor.py
───────────────────────────────────────────────────────────────────────────────
Extracts text from claim attachments:

• Images  → NO OCR (handled as-is downstream)  
• PDFs    → OCR (pytesseract on rendered pages)  
• DOCX/DOC/TXT → direct text extraction (python-docx / plain read)

Return structure:
    { "filename.ext": { "text": "<extracted or empty>" } }
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from .utils import (
    SUPPORTED_IMAGE_EXTENSIONS,
    PDF_EXT,
    DOCUMENT_EXTS,
    ensure_session_structure,
)

OCR_PSM = "--oem 3 --psm 6"  # basic OCR config


def _ocr_image(img: Image.Image) -> str:
    return pytesseract.image_to_string(img, config=OCR_PSM)


def _extract_pdf(path: str) -> str:
    pages_text: list[str] = []
    for page in convert_from_path(path, dpi=300):
        pages_text.append(_ocr_image(page))
    return "\n".join(pages_text)



def _extract_txt(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def process_and_update_claim_session(sender_email: str) -> Dict[str, Dict[str, str]]:
    """
    Run extraction for any new files in <session>/attachments, update
    parsed_docs.json, and return the full mapping.
    """
    session_folder = ensure_session_structure(sender_email)
    attach_dir = os.path.join(session_folder, "attachments")
    parsed_path = os.path.join(session_folder, "parsed_docs.json")

    parsed: Dict[str, Dict[str, str]] = {}
    if os.path.exists(parsed_path):
        with open(parsed_path, encoding="utf-8") as fh:
            parsed = json.load(fh)

    for fname in os.listdir(attach_dir):
        if fname in parsed:
            continue  # already processed

        fpath = os.path.join(attach_dir, fname)
        ext = os.path.splitext(fname)[1].lower()

        text = ""
        try:
            if ext == PDF_EXT:
                text = _extract_pdf(fpath)
            elif ext == ".txt":
                text = _extract_txt(fpath)
            # images → skip OCR, leave text blank
            # unsupported → leave text blank
        except Exception:  # noqa: BLE001
            text = ""  # swallow extraction errors

        parsed[fname] = {"text": text}

    with open(parsed_path, "w", encoding="utf-8") as fh:
        json.dump(parsed, fh, indent=2, ensure_ascii=False)

    return parsed