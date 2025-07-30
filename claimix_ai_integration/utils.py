"""
utils.py – Common helpers and constants used across the claim-processing
code-base.

The file is intentionally kept as a *single module* to avoid circular imports
and to provide a canonical place for IO / path utilities and shared constants.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
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
# Session / claim helpers
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

# ────────────────────────────────────────────────────────────────────────────
# Public exports
# ────────────────────────────────────────────────────────────────────────────

__all__: List[str] = [
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
    # session / claim helpers
    "generate_thread_id",
    "get_session_folder",
    "get_claim_file",
    "load_claim_state",
    "save_claim_state",
    "ensure_session_structure",
    # attachment helpers
    "is_document",
    "load_processed",
    "save_processed",
]