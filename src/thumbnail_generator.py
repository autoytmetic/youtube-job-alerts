"""
src/thumbnail_generator.py — Generates eye-catching YouTube thumbnails using Pillow.
Produces a 1280×720 JPEG with bold job title, salary, and branding.
"""

import logging
import textwrap
import random
import urllib.request
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from config import Config

logger = logging.getLogger(__name__)

# ── Color Schemes ─────────────────────────────────────────────────────────────
COLOR_SCHEMES = [
    {   # Red & Gold (high attention)
        "bg_top":     (180, 0, 0),
        "bg_bottom":  (90, 0, 0),
        "accent":     (255, 200, 0),
        "text_main":  (255, 255, 255),
        "text_sub":   (255, 230, 100),
        "badge_bg":   (255, 200, 0),
        "badge_text": (0, 0, 0),
    },
    {   # Navy & Orange
        "bg_top":     (0, 30, 100),
        "bg_bottom":  (0, 10, 60),
        "accent":     (255, 130, 0),
        "text_main":  (255, 255, 255),
        "text_sub":   (200, 220, 255),
        "badge_bg":   (255, 130, 0),
        "badge_text": (255, 255, 255),
    },
    {   # Dark Green & Yellow
        "bg_top":     (0, 80, 20),
        "bg_bottom":  (0, 40, 10),
        "accent":     (255, 220, 0),
        "text_main":  (255, 255, 255),
        "text_sub":   (200, 255, 200),
        "badge_bg":   (255, 220, 0),
        "badge_text": (0, 0, 0),
    },
]

# ── Font Management ────────────────────────────────────────────────────────────
FONT_URLS = {
    "bold":    "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf",
    "regular": "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf",
    "black":   "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Black.ttf",
}
# Fallback: system fonts available on Ubuntu / GitHub Actions runner
SYSTEM_FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font. Priority: cached Roboto → download Roboto → system font → PIL default.
    """
    font_path = Config.FONTS_DIR / f"Roboto-{name.capitalize()}.ttf"

    # 1. Try cached Roboto
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass

    # 2. Try downloading Roboto
    try:
        url = FONT_URLS.get(name.lower(), FONT_URLS["bold"])
        urllib.request.urlretrieve(url, str(font_path))
        return ImageFont.truetype(str(font_path), size)
    except Exception as e:
        logger.debug(f"Roboto download failed ({e}), trying system fonts.")

    # 3. Try system fonts (available on Ubuntu / GitHub Actions)
    for sys_path in SYSTEM_FONT_PATHS:
        if Path(sys_path).exists():
            try:
                return ImageFont.truetype(sys_path, size)
            except Exception:
                continue

    # 4. PIL built-in fallback
    return ImageFont.load_default()


class ThumbnailGenerator:
    """Creates YouTube thumbnails with bold job info overlays."""

    def generate(self, job: dict, output_path: str) -> str:
        """
        Generate a 1280×720 thumbnail for the given job.
        Returns the output_path.
        """
        W, H   = 1280, 720
        scheme = random.choice(COLOR_SCHEMES)

        # ── Canvas with gradient background ───────────────────────────────
        img  = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        self._draw_gradient(draw, W, H, scheme["bg_top"], scheme["bg_bottom"])

        # ── Decorative accent stripe ───────────────────────────────────────
        draw.rectangle([(0, 0), (18, H)], fill=scheme["accent"])
        draw.rectangle([(W - 18, 0), (W, H)], fill=scheme["accent"])

        # ── Top badge: SOURCE ─────────────────────────────────────────────
        source = job.get("source", "SARKARI JOB").upper()
        self._draw_badge(draw, source, x=50, y=40,
                         bg=scheme["badge_bg"], fg=scheme["badge_text"],
                         font=_get_font("bold", 28))

        # ── Main job title ────────────────────────────────────────────────
        title      = job.get("title", "Government Job Vacancy 2026")
        title_font = _get_font("black", 62)
        wrapped    = textwrap.fill(title, width=24)
        self._draw_text_with_shadow(draw, wrapped, x=W // 2, y=180,
                                    font=title_font, fill=scheme["text_main"],
                                    anchor="mm")

        # ── Salary highlight strip ─────────────────────────────────────────
        salary     = job.get("salary", "₹25,000+/month")
        sal_clean  = salary.replace("per month", "/month").replace("Per Month", "/month")
        sal_text   = f"💰 {sal_clean}"
        sal_font   = _get_font("bold", 44)
        # Draw highlight box
        sal_bbox   = draw.textbbox((0, 0), sal_text, font=sal_font)
        sw, sh     = sal_bbox[2] - sal_bbox[0], sal_bbox[3] - sal_bbox[1]
        pad        = 20
        box_x1     = (W - sw - pad * 2) // 2
        draw.rounded_rectangle(
            [(box_x1, 420), (box_x1 + sw + pad * 2, 420 + sh + pad)],
            radius=12, fill=scheme["accent"]
        )
        draw.text((W // 2, 435 + sh // 2), sal_text,
                  font=sal_font, fill=scheme["badge_text"], anchor="mm")

        # ── Deadline ──────────────────────────────────────────────────────
        deadline   = job.get("deadline", "Apply Soon")
        dead_text  = f"⏰ Last Date: {deadline}"
        dead_font  = _get_font("bold", 34)
        self._draw_text_with_shadow(draw, dead_text, x=W // 2, y=530,
                                    font=dead_font, fill=scheme["text_sub"],
                                    anchor="mm")

        # ── Bottom CTA bar ────────────────────────────────────────────────
        draw.rectangle([(0, H - 90), (W, H)], fill=scheme["accent"])
        cta_font = _get_font("bold", 38)
        draw.text((W // 2, H - 45), "APPLY NOW — LINK IN DESCRIPTION",
                  font=cta_font, fill=scheme["badge_text"], anchor="mm")

        # ── Save ──────────────────────────────────────────────────────────
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        logger.debug(f"Thumbnail saved → {output_path}")
        return output_path

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _draw_gradient(draw: ImageDraw.Draw, W: int, H: int,
                       top: Tuple, bottom: Tuple):
        for y in range(H):
            t = y / H
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

    @staticmethod
    def _draw_badge(draw: ImageDraw.Draw, text: str, x: int, y: int,
                    bg: Tuple, fg: Tuple, font: ImageFont.FreeTypeFont):
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad  = 10
        draw.rounded_rectangle(
            [(x, y), (x + w + pad * 2, y + h + pad)],
            radius=8, fill=bg
        )
        draw.text((x + pad, y + pad // 2), text, font=font, fill=fg)

    @staticmethod
    def _draw_text_with_shadow(draw: ImageDraw.Draw, text: str,
                                x: int, y: int, font, fill: Tuple,
                                anchor: str = "mm", shadow_offset: int = 3):
        # Draw shadow
        draw.text((x + shadow_offset, y + shadow_offset), text,
                  font=font, fill=(0, 0, 0, 160), anchor=anchor)
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill, anchor=anchor)
