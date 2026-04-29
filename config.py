"""
config.py — Central configuration for the YouTube Job Alert Generator.
All settings are read from environment variables (set via .env or GitHub Secrets).
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists (local development)
load_dotenv()

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent


class Config:
    # ── Directories ───────────────────────────────────────────────────────────
    ROOT_DIR        = ROOT_DIR
    OUTPUT_DIR      = ROOT_DIR / "output"
    CACHE_DIR       = ROOT_DIR / "cache" / "images"
    DATA_DIR        = ROOT_DIR / "data"
    ASSETS_DIR      = ROOT_DIR / "assets"
    FONTS_DIR       = ROOT_DIR / "assets" / "fonts"
    BG_DIR          = ROOT_DIR / "assets" / "backgrounds"

    # ── Pipeline Control ──────────────────────────────────────────────────────
    MAX_VIDEOS_PER_RUN     = int(os.getenv("MAX_VIDEOS_PER_RUN", "4"))
    YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "true").lower() == "true"

    # ── Processed Jobs Store ──────────────────────────────────────────────────
    PROCESSED_JOBS_FILE = DATA_DIR / "processed_jobs.json"

    # ── YouTube API ───────────────────────────────────────────────────────────
    YOUTUBE_CLIENT_SECRETS_FILE = os.getenv(
        "YOUTUBE_CLIENT_SECRETS_FILE", str(ROOT_DIR / "client_secrets.json")
    )
    YOUTUBE_TOKEN_FILE = str(ROOT_DIR / "token.json")
    YOUTUBE_SCOPES     = ["https://www.googleapis.com/auth/youtube.upload"]

    # ── Pixabay API ───────────────────────────────────────────────────────────
    PIXABAY_API_KEY   = os.getenv("PIXABAY_API_KEY", "")
    PIXABAY_BASE_URL  = "https://pixabay.com/api/"
    IMAGE_CACHE_LIMIT = 30   # max images cached locally

    # ── TTS ───────────────────────────────────────────────────────────────────
    TTS_LANGUAGE = "en"
    TTS_TLD      = "co.in"   # Indian English accent

    # ── Video ─────────────────────────────────────────────────────────────────
    VIDEO_WIDTH    = 1280
    VIDEO_HEIGHT   = 720
    VIDEO_FPS      = 24
    TARGET_DURATION = 60     # seconds

    # ── Scraper ───────────────────────────────────────────────────────────────
    SCRAPER_TIMEOUT   = 15   # seconds per request
    SCRAPER_MAX_JOBS  = 20   # max jobs to scrape per source per run
    SCRAPER_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    @classmethod
    def ensure_dirs(cls):
        """Create all required directories."""
        for d in [cls.OUTPUT_DIR, cls.CACHE_DIR, cls.DATA_DIR,
                  cls.ASSETS_DIR, cls.FONTS_DIR, cls.BG_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """Warn about missing optional configs."""
        if not cls.PIXABAY_API_KEY:
            logger.warning("PIXABAY_API_KEY not set — will use fallback background images.")
        if cls.YOUTUBE_UPLOAD_ENABLED and not Path(cls.YOUTUBE_CLIENT_SECRETS_FILE).exists():
            logger.warning(
                f"YouTube client_secrets.json not found at {cls.YOUTUBE_CLIENT_SECRETS_FILE}. "
                "Upload will be skipped."
            )
