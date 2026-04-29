"""
src/tts.py — Text-to-Speech using gTTS (Google Text-to-Speech, free tier).
Produces an MP3 file from a text script.
"""

import time
import logging
from pathlib import Path

from gtts import gTTS
from gtts.tts import gTTSError

from config import Config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class TTSGenerator:
    """Wrapper around gTTS for Indian-English narration."""

    def generate(self, text: str, output_path: str) -> str:
        """
        Convert `text` to speech and save MP3 at `output_path`.
        Returns the output_path on success.
        Raises RuntimeError if all retries fail.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                tts = gTTS(
                    text     = text,
                    lang     = Config.TTS_LANGUAGE,
                    tld      = Config.TTS_TLD,   # "co.in" → Indian English accent
                    slow     = False,
                )
                tts.save(str(output))
                logger.debug(f"TTS saved to {output}")
                return str(output)

            except gTTSError as e:
                logger.warning(f"gTTS attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    raise RuntimeError(f"TTS generation failed after {MAX_RETRIES} attempts: {e}")

            except Exception as e:
                raise RuntimeError(f"Unexpected TTS error: {e}")
