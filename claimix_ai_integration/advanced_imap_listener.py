from __future__ import annotations

"""
advanced_imap_listener.py
──────────────────────────────────────────────────────────────────────────────
• Polls the IMAP inbox.
• Stores acceptable attachments.
• Hands the message off to `orchestrator.orchestrate()`.

Thread-routing logic:
  Every e-mail is grouped by the root Message-ID of its conversation
  (References → In-Reply-To → Message-ID).  This lets the same sender
  have multiple concurrent claims without folder collisions.
"""
import os
import sys
import json
import time
import logging
import traceback
import shutil
import hashlib
import re  # <-- Added for regex
from email.utils import parseaddr
from datetime import datetime
from typing import List, Dict, Any, Optional

from imap_tools import MailBox, AND
from dotenv import load_dotenv

from .utils import (
get_session_folder, is_document,
load_processed, save_processed, load_json,MAX_ATTACHMENT_SIZE,
get_claim_session_folder,
normalize_subject, subject_fingerprint, claim_session_path_for_id,
)
from .email_utils import send_email
from .orchestrator import orchestrate

# ────────────────────────  environment  ──────────────────────────
load_dotenv()
IMAP_HOST     = os.getenv("IMAP_HOST", "")
IMAP_PORT     = int(os.getenv("IMAP_PORT", 993))
IMAP_USERNAME = os.getenv("IMAP_USERNAME", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ───────────────────  header-helper (robust)  ────────────────────
def _collapse(val) -> str:
    """
    Normalise an arbitrary header value to a single string.
      • str            → unchanged
      • list / tuple   → joined with spaces
      • other          → str(val)
    """
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)):
        return " ".join(map(str, val))
    return str(val)


def get_header(msg, name: str) -> str:
    """
    Case-insensitive header lookup that works with all imap-tools versions.
    Handles:
      • dict                        {'Subject': '…'}
      • list[tuple]                 [('Subject', '…'), …]
      • list[str]                   ['Subject: …', …]
    Returns '' when the header is missing.
    """
    name_lc = name.lower()
    hdrs = msg.headers

    # dict style ------------------------------------------------------------
    if isinstance(hdrs, dict):
        for k, v in hdrs.items():
            if isinstance(k, str) and k.lower() == name_lc:
                return _collapse(v).strip()

    # iterable style --------------------------------------------------------
    if isinstance(hdrs, (list, tuple)):
        for item in hdrs:
            # tuple ('Key', 'Value')
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                k, v = item[0], item[1]
                if isinstance(k, str) and k.lower() == name_lc:
                    return _collapse(v).strip()
            # raw string "Key: Value"
            elif isinstance(item, str) and ":" in item:
                k, v = item.split(":", 1)
                if k.lower().strip() == name_lc:
                    return _collapse(v).strip()

    return ""


def extract_root_id(msg) -> str:
    """
    Anchor the whole reply chain to a single ID.
      1. First token in 'References'
      2. 'In-Reply-To'
      3. Own 'Message-ID'   (new conversation)
    """
    refs = get_header(msg, "References")
    if refs:
        root = refs.split()[0]
        if root:
            return root

    in_reply = get_header(msg, "In-Reply-To")
    if in_reply:
        return in_reply

    msg_id = get_header(msg, "Message-ID")
    return msg_id or "no-msg-id"

def _extract_claim_id_from_subject(subject: str) -> Optional[str]:
    """
    Find a CLM-id token like 'CLM-abc123def0' in the subject.
    Returns the token (as-is) or None.
    """
    if not subject:
        return None
    m = re.search(r"\bCLM-[A-Za-z0-9-]{6,}\b", subject, flags=re.IGNORECASE)
    return m.group(0) if m else None

def _session_exists_for_claim(claim_id: str) -> bool:
    """
    Check if a session folder for claim_id already exists without creating it.
    """
    path = claim_session_path_for_id(claim_id)
    return os.path.isdir(path)

def find_claim_by_fingerprint(sender_email: str, normalized_subj: str) -> Optional[str]:
    """
    Scan sessions to find a claim with matching (sender_email, subject_fp).
    Returns claim_id or None. Only returns when exactly one match is found.
    """
    if not normalized_subj or not sender_email:
        return None
    fp = subject_fingerprint(sender_email, normalized_subj)
    candidates = []
    for name in os.listdir(SESSIONS_DIR):
        if not name.startswith("claim"):
            continue
        cdir = os.path.join(SESSIONS_DIR, name)
        cfile = os.path.join(cdir, "claim.json")
        if not os.path.isfile(cfile):
            continue
        try:
            data = load_json(cfile, default={}) or {}
            if data.get("sender_email") == sender_email and data.get("subject_fp") == fp:
                candidates.append(data.get("claim_id") or name.replace("claim_", ""))
        except Exception:
            continue
    return candidates[0] if len(candidates) == 1 else None

def last_active_claim_for_sender(sender_email: str) -> Optional[str]:
    """
    If the sender has exactly one non-COMPLETE claim, return its claim_id; else None.
    """
    if not sender_email:
        return None
    candidates = []
    for name in os.listdir(SESSIONS_DIR):
        if not name.startswith("claim"):
            continue
        cdir = os.path.join(SESSIONS_DIR, name)
        cfile = os.path.join(cdir, "claim.json")
        if not os.path.isfile(cfile):
            continue
        try:
            data = load_json(cfile, default={}) or {}
            if data.get("sender_email") != sender_email:
                continue
            stage = data.get("stage") or ""
            if stage == "COMPLETE":
                continue
            updated_at = data.get("updated_at") or data.get("created_at") or ""
            candidates.append((updated_at, data.get("claim_id") or name.replace("claim_", "")))
        except Exception:
            continue
    if len(candidates) == 1:
        return candidates[0][1]
    return None

def _new_claim_id() -> str:
    import uuid
    return f"CLM-{uuid.uuid4().hex[:10].upper()}"

# ───────────────────────  attachment helper  ───────────────────────
def _save_attachments(message, session_folder: str):
    """Persist attachments that meet type/size rules; return list of filenames."""
    stored = []
    attach_dir = os.path.join(session_folder, "attachments")
    os.makedirs(attach_dir, exist_ok=True)  # <-- Ensure directory exists
    for att in message.attachments:
        if not is_document(att) or att.size > MAX_ATTACHMENT_SIZE:
            continue
        fname = (att.filename or "attachment").replace("/", "_")
        path  = os.path.join(attach_dir, fname)
        with open(path, "wb") as fh:
            fh.write(att.payload)
        stored.append(fname)
    return stored

# ───────────────────────  main polling loop  ───────────────────────
def check_required_env_vars():
    """Check if all required environment variables are set."""
    required_vars = [
        'IMAP_HOST', 'IMAP_USERNAME', 'IMAP_PASSWORD',
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD'
    ]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print("\n[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these variables before running the listener.")
        return False
    # EMAIL_FROM is recommended but optional (fallback to SMTP_USER)
    if not os.getenv("EMAIL_FROM"):
        print("[WARN] EMAIL_FROM is not set; will default to SMTP_USER as From address.")
    return True

def _stable_claim_id_from_root(root_id: str) -> str:
    # Normalize and hash the thread root-id to get a stable claim id
    norm = (root_id or "").strip().strip("<>").strip().lower()
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]
    return f"CLM-{digest}"

def poll_inbox(interval_s: int = 10):
    """
    Main loop: fetch unseen messages, route them, mark UIDs processed.
    Conversation grouping is based on the root Message-ID.
    """
    print("\n" + "="*60)
    print("   CLAIMIX IMAP LISTENER STARTING")
    print("="*60)
    
    # Check environment variables first
    if not check_required_env_vars():
        return
        
    print("\n[CONFIG] Environment variables check passed")
    print(f"[CONFIG] IMAP Server: {os.getenv('IMAP_HOST')}")
    print(f"[CONFIG] SMTP Server: {os.getenv('SMTP_HOST')}:{os.getenv('SMTP_PORT')}")
    print(f"[CONFIG] Checking for new emails every {interval_s} seconds...")
    
    # Ensure sessions directory exists
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        print(f"[IMAP] Using session directory: {SESSIONS_DIR}")
    except Exception as e:
        print(f"[IMAP ERROR] Failed to create session directory: {e}")
        return
    
    while True:
        print("\n" + "-"*40)
        print(f"[IMAP] Checking for new messages at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
        mb = None
        try:
            print(f"[IMAP] Connecting to {IMAP_HOST} as {IMAP_USERNAME}...")
            mb = MailBox(IMAP_HOST, port=IMAP_PORT)
            mb.login(IMAP_USERNAME, IMAP_PASSWORD, initial_folder="INBOX")
            print("[IMAP] Connected successfully")
            
            # Fetch unread messages
            print("[IMAP] Fetching unread messages...")
            messages = list(mb.fetch(AND(seen=False), mark_seen=True))
            print(f"[IMAP] Found {len(messages)} unread message(s)")
            
            for msg in messages:
                try:
                    uid = str(msg.uid)
                    print(f"\n[IMAP] Processing message UID: {uid}")
                    
                    if uid in load_processed():
                        print(f"[IMAP] Message {uid} already processed, skipping...")
                        continue

                    # Normalize sender email
                    sender_raw = msg.from_
                    sender = parseaddr(sender_raw)[1] or sender_raw
                    print(f"[IMAP] From: {sender}")

                    # Prefer plain text; fallback to HTML if needed
                    body = msg.text or msg.html or ""
                    print(f"[IMAP] Body length: {len(body)} characters")

                    # Stable claim id by thread root-id
                                    # Subject and sender
                    subject = get_header(msg, "Subject") or ""
                    sender_raw = msg.from_
                    sender = parseaddr(sender_raw)[1] or sender_raw
                    print(f"[IMAP] From: {sender}")
                    print(f"[IMAP] Subject: {subject}")

                    # Body
                    body = msg.text or msg.html or ""
                    print(f"[IMAP] Body length: {len(body)} characters")

                    # Resolve claim_id (Option A rules)
                    claim_id = None

                    # 1) Subject tag
                    tagged_id = _extract_claim_id_from_subject(subject)
                    if tagged_id and _session_exists_for_claim(tagged_id):
                        claim_id = tagged_id

                    # 2) Subject fingerprint fallback
                    if claim_id is None:
                        norm_subj = normalize_subject(subject)
                        print(f"[DEBUG] Normalized subject: {norm_subj}")
                        fp = subject_fingerprint(sender, norm_subj)
                        print(f"[DEBUG] Subject fingerprint: {fp}")
                        fp_claim = find_claim_by_fingerprint(sender, norm_subj)  # <-- Fixed function name
                        if fp_claim:
                            claim_id = fp_claim

                    # 3) Last-active-per-sender fallback
                    if claim_id is None and not norm_subj.strip():
                        last_claim = last_active_claim_for_sender(sender)  # <-- Fixed function name
                        if last_claim:
                            claim_id = last_claim

                    # 4) Mint new claim_id if still unknown
                    if claim_id is None:
                        claim_id = _new_claim_id()
                        print(f"[IMAP] Minted new claim ID: {claim_id}")
                    else:
                        print(f"[IMAP] Resolved claim ID: {claim_id}")

                    # Create session folder and save attachments
                    session_folder = get_claim_session_folder(claim_id)
                    print(f"[IMAP] Using session folder: {session_folder}")

                    attachments = _save_attachments(msg, session_folder)
                    if attachments:
                        print(f"[IMAP] Saved {len(attachments)} attachment(s)")

                    # Pass to orchestrator (provide subject so it can persist subject_fp)
                    print(f"[IMAP] Calling orchestrator for claim {claim_id} from {sender}")
                    try:
                        orchestrate(
                            sender_email=sender,
                            user_message=body,
                            attachments=attachments,
                            claim_id=claim_id,
                            subject=subject
                        )
                        print("[IMAP] Orchestration completed successfully")
                    except Exception as e:
                        print(f"[IMAP ERROR] Error processing message: {str(e)}", file=sys.stderr)
                        traceback.print_exc()
                        
                    # Mark as processed (current behavior: regardless of orchestration result)
                    save_processed(uid)
                    print(f"[IMAP] Marked message {uid} as processed")
                    
                except Exception as msg_error:
                    logging.error(f"[IMAP ERROR] Error processing message: {msg_error}", exc_info=True)
                    logging.error(f"[IMAP] Error details: {traceback.format_exc()}")
            
        except Exception as exc:
            logging.error(f"[IMAP FATAL ERROR] {exc}")
            logging.error(f"[IMAP] Error details: {traceback.format_exc()}")
            print(f"[IMAP] Will retry in {interval_s} seconds...")
        finally:
            if mb:
                try:
                    mb.logout()
                except Exception as e:
                    print(f"[IMAP WARNING] Error during logout: {e}")

        time.sleep(interval_s)

# ─────────────────────────  CLI entrypoint  ─────────────────────────
if __name__ == "__main__":
    poll_inbox()