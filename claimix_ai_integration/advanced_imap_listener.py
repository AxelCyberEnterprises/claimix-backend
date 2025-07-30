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

from __future__ import annotations
import os, time, smtplib, ssl
from email.message import EmailMessage
from dotenv import load_dotenv
from imap_tools import AND, MailBox

from utils import (
    get_session_folder, is_document,
    load_processed, save_processed,
    MAX_ATTACHMENT_SIZE,
)
from orchestrator import orchestrate

# ────────────────────────  environment  ──────────────────────────
load_dotenv()
IMAP_HOST     = os.getenv("IMAP_HOST", "")
IMAP_PORT     = int(os.getenv("IMAP_PORT", 993))
IMAP_USER     = os.getenv("IMAP_USERNAME", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))          # STARTTLS default

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

# ──────────────────────  SMTP helper (unchanged)  ─────────────────────
def send_email(to: str, subject: str, html: str, *, retry: bool = True) -> bool:
    """
    Send an HTML e-mail using STARTTLS on port 587. One optional retry.
    """
    msg = EmailMessage()
    msg["From"] = IMAP_USER
    msg["To"] = to
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg.set_content("Please use an HTML-capable e-mail client.")
    msg.add_alternative(html, subtype="html")

    attempts_left = 2 if retry else 1
    while attempts_left:
        attempts_left -= 1
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                if not server.has_extn("STARTTLS"):
                    raise smtplib.SMTPException("Server lacks STARTTLS")
                ctx = ssl.create_default_context()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(IMAP_USER, IMAP_PASSWORD)
                server.send_message(msg)
            return True                               # success
        except smtplib.SMTPException as exc:
            print(f"[send_email] SMTP error: {exc}")
            if attempts_left:
                time.sleep(2)
    return False

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
def poll_inbox(interval_s: int = 10):
    """
    Main loop: fetch unseen messages, route them, mark UIDs processed.
    Conversation grouping is based on the root Message-ID.
    """
    while True:
        try:
            with MailBox(IMAP_HOST).login(IMAP_USER, IMAP_PASSWORD, initial_folder="INBOX") as mb:
                for msg in mb.fetch(AND(seen=False), mark_seen=True):
                    uid = str(msg.uid)
                    if uid in load_processed():
                        continue

                    sender = msg.from_ or ""
                    body   = msg.text or msg.html or ""

                    root_id = extract_root_id(msg)
                    composite_key = f"{sender}|{root_id}"

                    # session folder & attachments
                    session_folder = get_session_folder(composite_key)
                    attachments = _save_attachments(msg, session_folder)

                    try:
                        orchestrate(
                            email=composite_key,
                            user_message=body,
                            attachments=attachments
                        )
                    except Exception as exc:
                        print(f"[poll_inbox] orchestrator error UID {uid}: {exc}")

                    save_processed(uid)
        except Exception as exc:
            print(f"[poll_inbox] fatal inbox error: {exc}")

        time.sleep(interval_s)

# ─────────────────────────  CLI entrypoint  ─────────────────────────
if __name__ == "__main__":
    poll_inbox()