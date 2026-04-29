"""
YouTube Job Alert Generator - Main Orchestrator
Runs the full pipeline: Scrape → Script → TTS → Video → Upload
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from src.scraper import JobScraper
from src.script_generator import ScriptGenerator
from src.tts import TTSGenerator
from src.video_generator import VideoGenerator
from src.image_fetcher import ImageFetcher
from src.thumbnail_generator import ThumbnailGenerator
from src.youtube_uploader import YouTubeUploader
from src.utils import setup_logging, load_processed_jobs, save_processed_jobs

# ─── Setup ────────────────────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)
Config.ensure_dirs()


def run_pipeline(job: dict, idx: int) -> bool:
    """
    Run the full video generation pipeline for a single job.
    Returns True on success, False on failure.
    """
    job_id = job.get("id", f"job_{idx}")
    logger.info(f"[{idx+1}] Processing job: {job.get('title', 'Unknown')} | ID: {job_id}")

    output_dir = Config.OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path    = output_dir / "narration.mp3"
    video_path    = output_dir / "video.mp4"
    thumb_path    = output_dir / "thumbnail.jpg"

    try:
        # ── Step 1: Generate Script ────────────────────────────────────────
        logger.info("  [1/6] Generating script...")
        generator = ScriptGenerator()
        script    = generator.generate(job)
        logger.info(f"       Script ({len(script.split())} words): {script[:80]}...")

        # ── Step 2: Text-to-Speech ─────────────────────────────────────────
        logger.info("  [2/6] Generating TTS audio...")
        tts = TTSGenerator()
        tts.generate(script, str(audio_path))
        logger.info(f"       Audio saved → {audio_path}")

        # ── Step 3: Fetch Background Image ────────────────────────────────
        logger.info("  [3/6] Fetching background image...")
        fetcher = ImageFetcher()
        bg_path = fetcher.get_image(job.get("category", "job"))
        logger.info(f"       Image → {bg_path}")

        # ── Step 4: Generate Thumbnail ────────────────────────────────────
        logger.info("  [4/6] Generating thumbnail...")
        thumbnailer = ThumbnailGenerator()
        thumbnailer.generate(job, str(thumb_path))
        logger.info(f"       Thumbnail → {thumb_path}")

        # ── Step 5: Generate Video ────────────────────────────────────────
        logger.info("  [5/6] Generating video with FFmpeg...")
        video_gen = VideoGenerator()
        video_gen.generate(
            job        = job,
            script     = script,
            audio_path = str(audio_path),
            bg_path    = bg_path,
            output_path= str(video_path),
        )
        logger.info(f"       Video → {video_path}")

        # ── Step 6: Upload to YouTube ──────────────────────────────────────
        if Config.YOUTUBE_UPLOAD_ENABLED:
            logger.info("  [6/6] Uploading to YouTube...")
            uploader = YouTubeUploader()
            video_id = uploader.upload(
                job        = job,
                video_path = str(video_path),
                thumb_path = str(thumb_path),
            )
            logger.info(f"       Uploaded! YouTube ID: {video_id}")
            job["youtube_id"] = video_id
        else:
            logger.info("  [6/6] YouTube upload DISABLED (set YOUTUBE_UPLOAD_ENABLED=true to enable)")

        return True

    except Exception as e:
        logger.error(f"  ✗ Pipeline failed for job {job_id}: {e}")
        logger.debug(traceback.format_exc())
        return False


def main():
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("  YouTube Job Alert Generator — Starting Run")
    logger.info(f"  Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # ── 1. Scrape Jobs ────────────────────────────────────────────────────────
    logger.info("\n📡 Scraping jobs from sources...")
    scraper     = JobScraper()
    all_jobs    = scraper.scrape_all()
    logger.info(f"   Found {len(all_jobs)} total jobs")

    # ── 2. Filter Already Processed ──────────────────────────────────────────
    processed   = load_processed_jobs()
    new_jobs    = [j for j in all_jobs if j["id"] not in processed]
    logger.info(f"   {len(new_jobs)} new (unprocessed) jobs")

    if not new_jobs:
        logger.info("   No new jobs to process. Exiting.")
        return

    # ── 3. Limit to MAX_VIDEOS_PER_RUN ────────────────────────────────────────
    jobs_to_process = new_jobs[: Config.MAX_VIDEOS_PER_RUN]
    logger.info(f"   Processing {len(jobs_to_process)} job(s) this run\n")

    # ── 4. Run Pipeline for Each Job ──────────────────────────────────────────
    success_count = 0
    for idx, job in enumerate(jobs_to_process):
        ok = run_pipeline(job, idx)
        if ok:
            processed.add(job["id"])
            save_processed_jobs(processed)
            success_count += 1
        logger.info("")

    # ── 5. Summary ───────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    logger.info("=" * 60)
    logger.info(f"  ✅ Run complete: {success_count}/{len(jobs_to_process)} videos generated")
    logger.info(f"  ⏱  Total time: {elapsed}s ({elapsed//60}m {elapsed%60}s)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
