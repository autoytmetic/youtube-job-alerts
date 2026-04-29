"""
src/video_generator.py — Assembles a 16:9 ~60-second video using FFmpeg.

Pipeline:
  1. Measure audio duration
  2. Build a multi-slide layout (intro, details, salary, CTA) sized to audio
  3. Generate each slide as a PNG using Pillow
  4. Concatenate slides with FFmpeg + add audio + burned-in subtitles
"""

import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import Config
from src.thumbnail_generator import _get_font  # reuse font loader

logger = logging.getLogger(__name__)

W = Config.VIDEO_WIDTH   # 1280
H = Config.VIDEO_HEIGHT  # 720


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

def _ffprobe_duration(audio_path: str) -> float:
    """Return duration of audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path,
            ],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as e:
        logger.warning(f"ffprobe failed: {e} — using 60s default")
        return 60.0


def _run_ffmpeg(args: List[str]):
    """Run an FFmpeg command, raising RuntimeError on failure."""
    cmd = ["ffmpeg", "-y"] + args
    logger.debug("FFmpeg: " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg stderr:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg failed (code {result.returncode})")


# ── Slide Builder (Pillow) ─────────────────────────────────────────────────────

class SlideBuilder:
    """Creates individual PNG slide frames using Pillow."""

    BG_COLORS = {
        "intro":   ((10, 30, 90),  (0, 10, 50)),
        "details": ((15, 15, 15),  (30, 30, 50)),
        "salary":  ((80, 30, 0),   (30, 10, 0)),
        "cta":     ((0, 80, 20),   (0, 30, 10)),
    }
    ACCENT = (255, 200, 0)
    WHITE  = (255, 255, 255)
    YELLOW = (255, 220, 80)

    def _gradient_bg(self, slide_type: str) -> Image.Image:
        top, bot = self.BG_COLORS.get(slide_type, ((10, 10, 10), (30, 30, 30)))
        img  = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            r = int(top[0] + (bot[0] - top[0]) * t)
            g = int(top[1] + (bot[1] - top[1]) * t)
            b = int(top[2] + (bot[2] - top[2]) * t)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        return img

    def _blend_bg(self, bg_path: str, slide_type: str, alpha: float = 0.35) -> Image.Image:
        """Overlay the background image with a dark tint."""
        try:
            bg = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(3))
            overlay = self._gradient_bg(slide_type)
            return Image.blend(bg, overlay, alpha=1 - alpha)
        except Exception:
            return self._gradient_bg(slide_type)

    def build_intro(self, job: dict, bg_path: str, out_path: str):
        img  = self._blend_bg(bg_path, "intro")
        draw = ImageDraw.Draw(img)

        # Top accent bar
        draw.rectangle([(0, 0), (W, 8)],  fill=self.ACCENT)
        draw.rectangle([(0, H-8), (W, H)], fill=self.ACCENT)

        # Source badge
        source = job.get("source", "GOVT JOB").upper()
        self._badge(draw, source, 60, 30)

        # Main title
        title      = job.get("title", "Job Vacancy 2026")
        title_font = _get_font("black", 68)
        wrapped    = textwrap.fill(title, width=22)
        self._shadow_text(draw, wrapped, W // 2, H // 2 - 30,
                          title_font, self.WHITE, anchor="mm")

        # Tagline
        tag_font = _get_font("bold", 36)
        self._shadow_text(draw, "📢  New Recruitment Notification!",
                          W // 2, H // 2 + 130, tag_font, self.YELLOW, anchor="mm")

        img.save(out_path, "PNG")

    def build_details(self, job: dict, bg_path: str, out_path: str):
        img  = self._blend_bg(bg_path, "details")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (W, 8)], fill=self.ACCENT)

        # Section header
        hdr_font = _get_font("bold", 42)
        self._shadow_text(draw, "📋  JOB DETAILS", W // 2, 60,
                          hdr_font, self.ACCENT, anchor="mm")

        # Detail rows
        details = [
            ("🏢  Organization",  job.get("company",  "Government of India")),
            ("📌  Post",          job.get("title",    "Vacancy")[:55]),
            ("💼  Eligibility",   _detect_qualification(job.get("title", ""))),
            ("🌐  Source",        job.get("source",   "Official Portal")),
        ]
        lbl_font = _get_font("bold",    34)
        val_font = _get_font("regular", 32)

        y_start = 150
        for lbl, val in details:
            draw.text((80, y_start), lbl, font=lbl_font, fill=self.YELLOW)
            draw.text((500, y_start), val[:55], font=val_font, fill=self.WHITE)
            y_start += 70

        img.save(out_path, "PNG")

    def build_salary(self, job: dict, out_path: str):
        img  = self._gradient_bg("salary")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (W, 8)], fill=self.ACCENT)

        # Header
        hdr_font = _get_font("black", 52)
        self._shadow_text(draw, "💰  SALARY PACKAGE", W // 2, 100,
                          hdr_font, self.ACCENT, anchor="mm")

        # Big salary display
        salary    = job.get("salary", "As per govt norms")
        sal_font  = _get_font("black", 80)
        wrapped   = textwrap.fill(salary, width=20)
        self._shadow_text(draw, wrapped, W // 2, H // 2,
                          sal_font, self.WHITE, anchor="mm")

        # Perks line
        perk_font = _get_font("bold", 32)
        self._shadow_text(draw, "+ HRA  •  DA  •  Medical  •  Pension  •  Leave",
                          W // 2, H - 100, perk_font, self.YELLOW, anchor="mm")

        img.save(out_path, "PNG")

    def build_cta(self, job: dict, out_path: str):
        img  = self._gradient_bg("cta")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (W, 8)], fill=self.ACCENT)
        draw.rectangle([(0, H-8), (W, H)], fill=self.ACCENT)

        # Deadline
        deadline  = job.get("deadline", "Apply Soon")
        dead_font = _get_font("bold", 48)
        self._shadow_text(draw, f"⏰  Last Date: {deadline}",
                          W // 2, 120, dead_font, self.YELLOW, anchor="mm")

        # CTA main text
        cta_font = _get_font("black", 74)
        self._shadow_text(draw, "APPLY NOW!", W // 2, H // 2 - 30,
                          cta_font, self.WHITE, anchor="mm")

        # Sub instruction
        sub_font = _get_font("bold", 36)
        self._shadow_text(draw, "Link in Description  |  Subscribe for more alerts",
                          W // 2, H // 2 + 90, sub_font, self.YELLOW, anchor="mm")

        img.save(out_path, "PNG")

    # ── Shared drawing helpers ─────────────────────────────────────────────────

    def _badge(self, draw: ImageDraw.Draw, text: str, x: int, y: int):
        font = _get_font("bold", 28)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        p = 12
        draw.rounded_rectangle([(x, y), (x + w + p*2, y + h + p)],
                                radius=6, fill=self.ACCENT)
        draw.text((x + p, y + p//2), text, font=font, fill=(0, 0, 0))

    @staticmethod
    def _shadow_text(draw, text, x, y, font, fill, anchor="la", offset=3):
        draw.text((x + offset, y + offset), text,
                  font=font, fill=(0, 0, 0), anchor=anchor)
        draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


# ── Main VideoGenerator ────────────────────────────────────────────────────────

class VideoGenerator:
    """Assembles slides + audio into a final MP4 using FFmpeg."""

    def generate(self, job: dict, script: str,
                 audio_path: str, bg_path: str, output_path: str) -> str:
        """
        Build a ~60-second video and save to output_path.
        Returns output_path.
        """
        # Work in a temp dir to keep things clean
        with tempfile.TemporaryDirectory(prefix="yt_job_") as tmp:
            tmp = Path(tmp)
            builder = SlideBuilder()

            # ── 1. Get audio duration ──────────────────────────────────────
            duration = _ffprobe_duration(audio_path)
            logger.debug(f"Audio duration: {duration:.1f}s")

            # ── 2. Build slide timing (4 slides, proportional) ────────────
            # intro=25%, details=30%, salary=25%, cta=20%
            timings = [
                ("intro",   0.25),
                ("details", 0.30),
                ("salary",  0.25),
                ("cta",     0.20),
            ]
            slides = []
            for name, ratio in timings:
                dur  = round(duration * ratio, 2)
                path = str(tmp / f"slide_{name}.png")
                slides.append((name, dur, path))

            # ── 3. Render slide images ─────────────────────────────────────
            builder.build_intro(job, bg_path, slides[0][2])
            builder.build_details(job, bg_path, slides[1][2])
            builder.build_salary(job, slides[2][2])
            builder.build_cta(job, slides[3][2])

            # ── 4. Convert each slide PNG → silent MP4 clip ───────────────
            clip_paths = []
            for name, dur, img_path in slides:
                clip_path = str(tmp / f"clip_{name}.mp4")
                _run_ffmpeg([
                    "-loop",   "1",
                    "-i",      img_path,
                    "-t",      str(dur),
                    "-vf",     f"scale={W}:{H},fps={Config.VIDEO_FPS}",
                    "-c:v",    "libx264",
                    "-preset", "ultrafast",
                    "-tune",   "stillimage",
                    "-pix_fmt","yuv420p",
                    clip_path,
                ])
                clip_paths.append(clip_path)

            # ── 5. Concatenate clips ───────────────────────────────────────
            concat_list = tmp / "concat.txt"
            concat_list.write_text(
                "\n".join(f"file '{p}'" for p in clip_paths)
            )
            silent_video = str(tmp / "silent.mp4")
            _run_ffmpeg([
                "-f",       "concat",
                "-safe",    "0",
                "-i",       str(concat_list),
                "-c",       "copy",
                silent_video,
            ])

            # ── 6. Generate subtitle (.srt) ────────────────────────────────
            srt_path = str(tmp / "subs.srt")
            self._make_srt(script, duration, srt_path)

            # ── 7. Burn subtitles + merge audio ────────────────────────────
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Subtitle style: white bold text, black outline, bottom-center
            font_path = Config.FONTS_DIR / "Roboto-Bold.ttf"
            subs_filter = (
                f"subtitles={srt_path}:force_style='"
                f"Fontname=Roboto,Fontsize=18,Bold=1,"
                f"PrimaryColour=&Hffffff,OutlineColour=&H000000,"
                f"Outline=2,Shadow=1,Alignment=2,MarginV=40'"
            )

            _run_ffmpeg([
                "-i", silent_video,
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-vf", subs_filter,
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-pix_fmt", "yuv420p",
                output_path,
            ])

        logger.info(f"Video generated: {output_path}")
        return output_path

    # ── SRT helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _make_srt(script: str, duration: float, out_path: str):
        """
        Split script into subtitle chunks (~8 words each) and write .srt file.
        """
        words      = script.split()
        chunk_size = 8
        chunks     = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]
        n          = len(chunks)
        per_chunk  = duration / n if n else duration

        lines = []
        for idx, chunk in enumerate(chunks):
            start = idx * per_chunk
            end   = start + per_chunk
            lines.append(
                f"{idx + 1}\n"
                f"{_fmt_time(start)} --> {_fmt_time(end)}\n"
                f"{' '.join(chunk)}\n"
            )

        Path(out_path).write_text("\n".join(lines))


def _fmt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    ms  = int((seconds % 1) * 1000)
    s   = int(seconds)
    m   = s // 60
    h   = m // 60
    m  %= 60
    s  %= 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _detect_qualification(title: str) -> str:
    t = title.lower()
    if "10th" in t or "matric" in t:   return "10th Pass"
    if "12th" in t or "intermediate" in t: return "12th Pass"
    if "engineer" in t or "btech" in t: return "B.Tech / B.E."
    if "iti" in t or "diploma" in t:    return "ITI / Diploma"
    return "Any Graduate"
