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
from datetime import datetime
from typing import List, Dict, Any, Optional

from imap_tools import MailBox, AND
from dotenv import load_dotenv

from claimix_ai_integration.utils import (
    get_session_folder, is_document,
    load_processed, save_processed,
    MAX_ATTACHMENT_SIZE,
)
from claimix_ai_integration.email_utils import send_email
from claimix_ai_integration.orchestrator import orchestrate

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

# ───────────────────────  attachment helper  ───────────────────────
def _save_attachments(message, session_folder: str):
    """Persist attachments that meet type/size rules; return list of filenames."""
    stored = []
    attach_dir = os.path.join(session_folder, "attachments")
    for att in message.attachments:
        if not is_document(att) or att.size > MAX_ATTACHMENT_SIZE:
            continue
        fname = att.filename.replace("/", "_")
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
        'SMTP_SERVER', 'SMTP_PORT', 'EMAIL_FROM'
    ]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print("\n[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these variables before running the listener.")
        return False
    return True

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
    print(f"[CONFIG] SMTP Server: {os.getenv('SMTP_SERVER')}:{os.getenv('SMTP_PORT')}")
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

                    sender = msg.from_ or ""
                    print(f"[IMAP] From: {sender}")
                    
                    body = msg.text or msg.html or ""
                    print(f"[IMAP] Body length: {len(body)} characters")
                    
                    # Generate a new claim ID for this message
                    claim_id = f"CLM-{int(time.time())}"  # Simple timestamp-based ID
                    print(f"[IMAP] Generated claim ID: {claim_id}")
                    
                    # Create session folder using claim ID
                    session_folder = get_session_folder(claim_id)
                    print(f"[IMAP] Using session folder: {session_folder}")
                    
                    # Save attachments to the claim's session folder
                    attachments = _save_attachments(msg, session_folder)
                    if attachments:
                        print(f"[IMAP] Saved {len(attachments)} attachment(s)")

                    # Pass to orchestrator with claim ID
                    print("[IMAP] Passing message to orchestrator...")
                    try:
                        # Initialize the claim with basic info
                        claim_data = {
                            'claim_id': claim_id,
                            'sender_email': sender,  # Store sender's email
                            'description': body[:500],  # Truncate long descriptions
                            'status': 'New',
                            'created_at': datetime.now().isoformat(),
                            'updated_at': datetime.now().isoformat(),
                            'subject': msg.subject or 'No Subject'
                        }
                        
                        # Save initial claim data
                        claim_path = os.path.join(session_folder, 'claim.json')
                        os.makedirs(os.path.dirname(claim_path), exist_ok=True)
                        with open(claim_path, 'w') as f:
                            json.dump(claim_data, f, indent=2)
                        
                        print(f"[IMAP] Calling orchestrator for claim {claim_id} from {sender}")
                        # Call orchestrator with sender email and claim ID
                        orchestrate(
                            sender_email=sender,
                            user_message=body,
                            attachments=attachments,
                            claim_id=claim_id
                        )
                        print("[IMAP] Orchestration completed successfully")
                        
                    except Exception as e:
                        print(f"[IMAP ERROR] Error processing message: {str(e)}", file=sys.stderr)
                        traceback.print_exc()
                        
                        # Clean up session folder on error
                        if os.path.exists(session_folder):
                            print(f"[IMAP] Cleaning up session folder: {session_folder}")
                            try:
                                shutil.rmtree(session_folder, ignore_errors=True)
                            except Exception as e:
                                print(f"[IMAP ERROR] Failed to clean up session folder: {e}", file=sys.stderr)
                    
                    # Mark as processed even if there was an error, to prevent infinite retries
                    save_processed(uid)
                    print(f"[IMAP] Marked message {uid} as processed")
                    
                except Exception as msg_error:
                    import logging
                    logging.error(f"[IMAP ERROR] Error processing message: {msg_error}", exc_info=True)
                    logging.error(f"[IMAP] Error details: {traceback.format_exc()}")
            
        except Exception as exc:
            import logging
            import traceback
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