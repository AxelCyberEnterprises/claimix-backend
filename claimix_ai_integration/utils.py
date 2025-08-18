from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import re
from typing import Any, Dict, Iterable, List, Set

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

SESSIONS_DIR: str = os.getenv("SESSIONS_DIR", "sessions")
PROCESSED_FILE: str = "processed_emails.json"
MAX_ATTACHMENT_SIZE: int = 10 * 1024 * 1024  # 10 MB

DOCUMENT_EXTS: Set[str] = {
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
}

SUPPORTED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
PDF_EXT: str = ".pdf"

# Ensure root folders exist at import-time
pathlib.Path(SESSIONS_DIR, "attachments").mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────────────────────────────────
# Basic JSON helpers
# ────────────────────────────────────────────────────────────────────────────

def _ensure_parent_dir(path: str | pathlib.Path) -> None:
    pathlib.Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def load_json(path: str | pathlib.Path, *, default: Any | None = None) -> Any:
    """
    Load JSON from *path*.
    Returns *default* if the file does not exist.
    Raises on malformed JSON.
    """
    path = pathlib.Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str | pathlib.Path, data: Any, *, indent: int = 2) -> None:
    """Write *data* to *path* as pretty-printed UTF-8 JSON."""
    _ensure_parent_dir(path)
    with pathlib.Path(path).open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=False)


def retry_load_json(
    path: str | pathlib.Path,
    *,
    retries: int = 3,
    delay_s: float = 1.0,
    default: Any | None = None,
) -> Any:
    """
    Load JSON with retry/back-off.
    Useful when another process may still be writing the file.
    """
    path = pathlib.Path(path)
    for attempt in range(1, retries + 1):
        try:
            return load_json(path, default=default)
        except json.JSONDecodeError:
            if attempt == retries:
                raise
            time.sleep(delay_s)

# ────────────────────────────────────────────────────────────────────────────
# Session / claim helpers (legacy: email-thread based)
# ────────────────────────────────────────────────────────────────────────────

def generate_thread_id(email: str) -> str:
    """Return a stable 12-character thread id derived from lower-cased e-mail."""
    return hashlib.md5(email.lower().encode("utf-8")).hexdigest()[:12]


def get_session_folder(email: str) -> str:
    """Return (and create if needed) the session folder for *email*."""
    folder = pathlib.Path(SESSIONS_DIR, f"thread_{generate_thread_id(email)}")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "attachments").mkdir(exist_ok=True)
    return str(folder)


def get_claim_file(email: str) -> str:
    """
    Return absolute path to the claim.json for *email*,
    creating a stub if it does not yet exist.
    """
    path = pathlib.Path(get_session_folder(email)) / "claim.json"
    if not path.exists():
        save_json(path, {"stage": "NEW"})
    return str(path)


def load_claim_state(email: str) -> Dict[str, Any]:
    return load_json(get_claim_file(email), default={})


def save_claim_state(email: str, state: Dict[str, Any]) -> None:
    save_json(get_claim_file(email), state)


def ensure_session_structure(email: str, *, extra_dirs: Iterable[str] | None = None) -> str:
    """
    Guarantee that the standard session folder and attachments sub-folder exist.
    Optionally create additional sub-folders given in *extra_dirs*.
    Returns the absolute session path.
    """
    session_path = pathlib.Path(get_session_folder(email))
    if extra_dirs:
        for sub in extra_dirs:
            (session_path / sub).mkdir(exist_ok=True)
    return str(session_path)

# ────────────────────────────────────────────────────────────────────────────
# Claim-id centric helpers (canonical for new code)
# ────────────────────────────────────────────────────────────────────────────

def get_claim_session_folder(claim_id: str) -> str:
    """
    Canonical claim-id based session folder.
    Creates sessions/claim_<claim_id>/attachments and returns the session path.
    """
    safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", str(claim_id))
    folder = pathlib.Path(SESSIONS_DIR, f"claim_{safe_id}")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "attachments").mkdir(exist_ok=True)
    return str(folder)


def get_claim_file_by_id(claim_id: str) -> str:
    """
    Return absolute path to claim.json for a given claim_id,
    creating a stub if it does not yet exist.
    """
    path = pathlib.Path(get_claim_session_folder(claim_id)) / "claim.json"
    if not path.exists():
        save_json(path, {"stage": "NEW", "claim_id": str(claim_id)})
    return str(path)


def ensure_claim_session_structure_by_id(
    claim_id: str, *, extra_dirs: Iterable[str] | None = None
) -> str:
    """
    Ensure the standard session folder exists for claim_id.
    Optionally create extra sub-folders.
    """
    session_path = pathlib.Path(get_claim_session_folder(claim_id))
    if extra_dirs:
        for sub in extra_dirs:
            (session_path / sub).mkdir(exist_ok=True)
    return str(session_path)

# ────────────────────────────────────────────────────────────────────────────
# Attachment & processed-mail helpers
# ────────────────────────────────────────────────────────────────────────────

def is_document(filename_or_object) -> bool:
    """
    Return True if *filename_or_object* has an extension we consider a document.
    Accepts either an IMAP attachment object or a raw filename string.
    """
    if hasattr(filename_or_object, "filename"):
        filename = filename_or_object.filename or ""
    else:
        filename = str(filename_or_object)
    ext = os.path.splitext(filename)[1].lower()
    return ext in DOCUMENT_EXTS


def load_processed() -> Set[str]:
    """Return a set of already processed message UIDs."""
    return set(load_json(PROCESSED_FILE, default=[]))


def save_processed(uid: str) -> None:
    """Append *uid* to the processed list (idempotent)."""
    processed = load_processed()
    processed.add(str(uid))
    save_json(PROCESSED_FILE, list(processed))
def normalize_subject(subject: str) -> str:
    """
    Normalize the subject line for claim threading.
    - Removes claim tags and reply/forward prefixes.
    - Preserves key words to distinguish different claims.
    """
    s = subject.lower()
    # Remove claim ID tags like [CLM-...]
    s = re.sub(r"\[?clm-[a-z0-9-]+\]?", " ", s, flags=re.IGNORECASE)
    # Remove common reply/forward prefixes at the start
    s = re.sub(r"^(re|fwd|fw):\s*", "", s)
    # Remove extra whitespace
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s

def subject_fingerprint(sender_email: str, normalized_subject: str) -> str:
    """
    Compute a stable fingerprint for (sender_email, normalized_subject).
    Used only for fallback lookup — not as claim_id.
    """
    base = f"{(sender_email or '').lower()}|{normalized_subject or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def claim_session_path_for_id(claim_id: str) -> str:
    """
    Return the expected session folder path for a claim_id without creating it.
    """
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(claim_id))
    return str(pathlib.Path(SESSIONS_DIR, f"claim{safe_id}"))

all: List[str] = [
# constants
"SESSIONS_DIR",
"PROCESSED_FILE",
"MAX_ATTACHMENT_SIZE",
"DOCUMENT_EXTS",
"SUPPORTED_IMAGE_EXTENSIONS",
"PDF_EXT",
# JSON helpers
"load_json",
"save_json",
"retry_load_json",
# session / claim helpers (legacy + new)
"generate_thread_id",
"get_session_folder",
"get_claim_file",
"load_claim_state",
"save_claim_state",
"ensure_session_structure",
"get_claim_session_folder",
"get_claim_file_by_id",
"ensure_claim_session_structure_by_id",
"claim_session_path_for_id",
# subject helpers
"normalize_subject",
"subject_fingerprint",
# attachment helpers
"is_document",
"load_processed",
"save_processed",
]