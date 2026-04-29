"""
src/youtube_uploader.py — Uploads videos to YouTube using the Data API v3.

Authentication flow:
  • Local dev:  Interactive OAuth2 browser flow (stores token.json)
  • GitHub CI:  Reads token.json from YOUTUBE_TOKEN_JSON secret (base64 encoded)
"""

import json
import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import Config

logger = logging.getLogger(__name__)

MAX_RETRIES   = 3
RETRY_BACKOFF = [10, 30, 60]  # seconds between retries

# Category IDs: 27 = Education, 22 = People & Blogs, 10 = Music
YT_CATEGORY_ID = "27"   # Education


class YouTubeUploader:
    """Handles OAuth2 authentication and video upload to YouTube."""

    def __init__(self):
        self._service = None

    def upload(self, job: dict, video_path: str, thumb_path: str) -> str:
        """
        Upload a video to YouTube and set its thumbnail.
        Returns the YouTube video ID.
        """
        service  = self._get_service()
        metadata = self._build_metadata(job)

        logger.info(f"   Uploading: {metadata['snippet']['title'][:60]}...")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                video_id = self._upload_video(service, video_path, metadata)
                logger.info(f"   Uploaded video ID: {video_id}")

                # Upload thumbnail
                try:
                    self._upload_thumbnail(service, video_id, thumb_path)
                    logger.info("   Thumbnail uploaded.")
                except Exception as e:
                    logger.warning(f"   Thumbnail upload failed (non-fatal): {e}")

                return video_id

            except Exception as e:
                logger.error(f"   Upload attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt - 1]
                    logger.info(f"   Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"YouTube upload failed after {MAX_RETRIES} attempts: {e}")

    # ── Internal Methods ───────────────────────────────────────────────────────

    def _get_service(self):
        if self._service:
            return self._service

        creds = self._load_credentials()
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _load_credentials(self) -> Credentials:
        """
        Load OAuth credentials. Priority:
          1. YOUTUBE_TOKEN_JSON env var (base64-encoded token, for GitHub Actions)
          2. token.json file on disk
          3. Interactive OAuth flow (local dev only)
        """
        token_path = Path(Config.YOUTUBE_TOKEN_FILE)

        # ── GitHub Actions: read from env var ─────────────────────────────
        token_b64 = os.environ.get("YOUTUBE_TOKEN_JSON", "")
        if token_b64:
            try:
                token_data = base64.b64decode(token_b64).decode()
                token_path.write_text(token_data)
                logger.debug("Loaded token from YOUTUBE_TOKEN_JSON env var")
            except Exception as e:
                raise RuntimeError(f"Failed to decode YOUTUBE_TOKEN_JSON: {e}")

        # ── Load from file ─────────────────────────────────────────────────
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(token_path), Config.YOUTUBE_SCOPES
            )
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired YouTube token...")
                creds.refresh(Request())
                token_path.write_text(creds.to_json())
                return creds

        # ── Interactive OAuth (local dev only) ─────────────────────────────
        secrets_path = Path(Config.YOUTUBE_CLIENT_SECRETS_FILE)
        if not secrets_path.exists():
            raise FileNotFoundError(
                f"No OAuth credentials found.\n"
                f"  • For local dev: place client_secrets.json at {secrets_path}\n"
                f"  • For CI: set YOUTUBE_TOKEN_JSON secret (base64-encoded token.json)\n"
                "  See setup.md for full instructions."
            )

        logger.info("Starting OAuth2 browser flow (one-time setup)...")
        flow  = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path), Config.YOUTUBE_SCOPES
        )
        creds = flow.run_local_server(port=0, open_browser=True)
        token_path.write_text(creds.to_json())
        logger.info(f"Token saved to {token_path}")
        return creds

    def _build_metadata(self, job: dict) -> dict:
        """Build YouTube video metadata from job details."""
        title_raw  = job.get("title",   "Government Job Vacancy")
        company    = job.get("company", "Government of India")
        salary     = job.get("salary",  "")
        deadline   = job.get("deadline","")
        link       = job.get("link",    "")
        source     = job.get("source",  "")

        # Sanitize title to fit YouTube's 100-char limit
        yt_title = f"{title_raw[:60]} 2026 | {salary[:20] if salary else 'Govt Job'}"
        yt_title = yt_title[:100]

        description = (
            f"🔔 {title_raw}\n\n"
            f"🏢 Organization: {company}\n"
            f"💰 Salary: {salary}\n"
            f"⏰ Last Date: {deadline}\n"
            f"📋 Source: {source}\n\n"
            f"🔗 APPLY NOW: {link}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Subscribe for daily job alerts!\n"
            f"🔔 Turn on notifications so you never miss a vacancy.\n\n"
            f"Tags: #govtjob #sarkarinaukri #indianjobs #recruitment2026 "
            f"#jobvacancy #govtjobs2026\n"
        )

        tags = [
            "govt job", "government job 2026", "sarkari naukri",
            "india jobs", "job vacancy", "latest recruitment",
            "10th pass job", "12th pass job", "graduate job",
            job.get("source", "").lower(), "free job alert",
            "job alert india", "naukri 2026", "recruitment 2026",
        ]
        # Add company name as tag
        tags.append(company[:30].lower())

        return {
            "snippet": {
                "title":       yt_title,
                "description": description,
                "tags":        [t for t in tags if t],
                "categoryId":  YT_CATEGORY_ID,
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            },
        }

    @staticmethod
    def _upload_video(service, video_path: str, metadata: dict) -> str:
        """Execute the resumable upload and return the video ID."""
        media = MediaFileUpload(
            video_path,
            mimetype   = "video/mp4",
            resumable  = True,
            chunksize  = 1024 * 1024,   # 1 MB chunks
        )
        request = service.videos().insert(
            part       = "snippet,status",
            body       = metadata,
            media_body = media,
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.debug(f"   Upload progress: {pct}%")

        return response["id"]

    @staticmethod
    def _upload_thumbnail(service, video_id: str, thumb_path: str):
        """Upload thumbnail for an already-uploaded video."""
        media = MediaFileUpload(thumb_path, mimetype="image/jpeg")
        service.thumbnails().set(
            videoId    = video_id,
            media_body = media,
        ).execute()
