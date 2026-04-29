"""
src/image_fetcher.py — Fetches background images from Pixabay API with local caching.
Falls back to generating a solid-color gradient image if API key is unavailable.
"""

import json
import logging
import random
import hashlib
import urllib.request
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter

from config import Config

logger = logging.getLogger(__name__)

# Keyword groups used per job category
KEYWORD_MAP = {
    "bank job india":             ["bank office india", "banking finance"],
    "defence job india":          ["police uniform india", "security force"],
    "teacher job india":          ["teacher classroom india", "education school"],
    "medical job india":          ["hospital doctor india", "medical healthcare"],
    "engineering job office":     ["technology office computer", "engineering workspace"],
    "government job office india":["government office india", "official building"],
    "railway job india":          ["indian railway train", "railway station india"],
    "police job india":           ["police uniform india", "law enforcement"],
    "default":                    ["office hiring india", "job career professional"],
}


class ImageFetcher:
    """Fetches and caches background images for video generation."""

    def __init__(self):
        Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_image(self, category: str = "default") -> str:
        """
        Return a local path to a background image for the given category.
        Tries cache first, then Pixabay, then generates a fallback.
        """
        # ── 1. Try cache ───────────────────────────────────────────────────
        cached = self._find_cached(category)
        if cached:
            logger.debug(f"Using cached image: {cached}")
            return cached

        # ── 2. Try Pixabay ─────────────────────────────────────────────────
        if Config.PIXABAY_API_KEY:
            path = self._fetch_from_pixabay(category)
            if path:
                return path

        # ── 3. Generate fallback gradient ──────────────────────────────────
        logger.info("   Using generated fallback background image.")
        return self._generate_fallback(category)

    # ── Private ────────────────────────────────────────────────────────────────

    def _find_cached(self, category: str) -> Optional[str]:
        """Return a random existing cached image for this category."""
        pattern  = self._cache_prefix(category)
        matches  = list(Config.CACHE_DIR.glob(f"{pattern}*.jpg"))
        if matches:
            return str(random.choice(matches))
        return None

    def _cache_prefix(self, category: str) -> str:
        key = hashlib.md5(category.encode()).hexdigest()[:8]
        return f"img_{key}_"

    def _fetch_from_pixabay(self, category: str) -> Optional[str]:
        """Download a random image from Pixabay matching the category keywords."""
        keywords = KEYWORD_MAP.get(category, KEYWORD_MAP["default"])
        query    = random.choice(keywords)

        try:
            params = {
                "key":         Config.PIXABAY_API_KEY,
                "q":           query,
                "image_type":  "photo",
                "orientation": "horizontal",
                "min_width":   1280,
                "min_height":  720,
                "per_page":    10,
                "safesearch":  "true",
            }
            resp = requests.get(Config.PIXABAY_BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                logger.warning(f"Pixabay: no results for '{query}'")
                return None

            # Pick a random hit
            hit      = random.choice(hits[:5])
            img_url  = hit.get("webformatURL") or hit.get("largeImageURL")
            if not img_url:
                return None

            # Save with stable cache key
            prefix   = self._cache_prefix(category)
            uid      = hashlib.md5(img_url.encode()).hexdigest()[:8]
            save_path = Config.CACHE_DIR / f"{prefix}{uid}.jpg"

            urllib.request.urlretrieve(img_url, str(save_path))
            logger.info(f"   Downloaded image → {save_path.name}")

            # Prune old cache entries if too many
            self._prune_cache()
            return str(save_path)

        except Exception as e:
            logger.warning(f"Pixabay fetch failed: {e}")
            return None

    def _generate_fallback(self, category: str) -> str:
        """
        Generate a clean gradient background image (1280×720) using Pillow.
        No external network call required.
        """
        SCHEMES = [
            ((15, 32, 100),  (0, 0, 0)),     # dark blue → black
            ((26, 0, 51),    (77, 0, 128)),   # dark purple gradient
            ((0, 77, 0),     (0, 26, 0)),     # dark green
            ((100, 20, 0),   (30, 0, 0)),     # dark red/maroon
            ((0, 40, 80),    (0, 10, 40)),    # navy blue
        ]
        top_color, bot_color = random.choice(SCHEMES)

        img  = Image.new("RGB", (Config.VIDEO_WIDTH, Config.VIDEO_HEIGHT))
        draw = ImageDraw.Draw(img)
        h    = Config.VIDEO_HEIGHT

        for y in range(h):
            t = y / h
            r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
            g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
            b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
            draw.line([(0, y), (Config.VIDEO_WIDTH, y)], fill=(r, g, b))

        # Add subtle texture overlay
        img = img.filter(ImageFilter.GaussianBlur(0))

        prefix    = self._cache_prefix(category)
        save_path = Config.CACHE_DIR / f"{prefix}fallback.jpg"
        img.save(str(save_path), "JPEG", quality=90)
        return str(save_path)

    def _prune_cache(self):
        """Keep only the N most-recently-modified cached images."""
        images = sorted(
            Config.CACHE_DIR.glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in images[Config.IMAGE_CACHE_LIMIT:]:
            try:
                old.unlink()
            except Exception:
                pass
