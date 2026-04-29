"""
src/utils.py — Shared utility helpers.
"""

import json
import logging
import hashlib
from pathlib import Path
from config import Config


def setup_logging(level: str = "INFO"):
    """Configure root logger with clean format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler()],
    )
    # Quieten noisy third-party loggers
    for noisy in ("urllib3", "googleapiclient", "oauth2client", "httplib2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def make_job_id(title: str, company: str, source: str) -> str:
    """Generate a stable unique ID for a job posting."""
    raw = f"{source}|{title}|{company}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_processed_jobs() -> set:
    """Load the set of already-processed job IDs."""
    path = Config.PROCESSED_JOBS_FILE
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return set(data.get("ids", []))
        except Exception:
            pass
    return set()


def save_processed_jobs(processed: set):
    """Persist the set of processed job IDs."""
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Config.PROCESSED_JOBS_FILE.write_text(
        json.dumps({"ids": list(processed)}, indent=2)
    )


def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid in filenames."""
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
    return "".join(c if c in keep else "_" for c in name)[:80]


def clamp(val, lo, hi):
    return max(lo, min(hi, val))
