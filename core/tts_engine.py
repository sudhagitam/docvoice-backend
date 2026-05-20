"""
DocVoice AI – TTS Engine
Converts text to MP3 using gTTS with chunking, retry logic and rate-limit handling.
"""

import io
import logging
import os
import re
import textwrap
import time
import uuid
from pathlib import Path
from typing import Iterator, Optional

from core.config import settings
from core.exceptions import TTSError

logger = logging.getLogger("docvoice.tts")

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "te": "Telugu",
    "zh": "Chinese (Mandarin)",
    "ar": "Arabic",
    "ru": "Russian",
}

ENGLISH_ACCENTS: dict[str, str] = {
    "com":    "US English",
    "co.uk":  "UK English",
    "com.au": "Australian English",
    "co.in":  "Indian English",
    "ca":     "Canadian English",
}


class TTSEngine:
    """
    Converts plain text to MP3 audio using gTTS.

    Features:
    - Sentence-aware chunking for large documents
    - Automatic retry with exponential backoff on 429 rate limits
    - Delay between chunks to avoid hitting Google TTS rate limits
    - Multi-language + Telugu support
    """

    CHUNK_SIZE   = 3_000   # chars per gTTS request (smaller = less likely to hit limits)
    MAX_RETRIES  = 5       # max retry attempts per chunk
    RETRY_DELAY  = 5       # seconds between retries (doubles each attempt)
    CHUNK_DELAY  = 1.5     # seconds between chunks to avoid rate limiting

    def __init__(self, lang: str = "en", slow: bool = False, tld: str = "com"):
        self.lang = lang if lang in SUPPORTED_LANGUAGES else "en"
        self.slow = slow
        self.tld  = tld

    # ── Public API ────────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> bytes:
        """
        Convert text to MP3 bytes with retry + rate-limit handling.
        """
        if not text.strip():
            raise TTSError("Empty text passed to TTS engine.")

        chunks = list(self._chunk(text))
        logger.info(
            "Synthesising %d chunk(s), lang=%s, slow=%s",
            len(chunks), self.lang, self.slow
        )

        mp3_parts: list[bytes] = []
        for i, chunk in enumerate(chunks, 1):
            logger.info("Processing chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
            mp3_parts.append(self._gtts_chunk_with_retry(chunk, i, len(chunks)))

            # Delay between chunks to respect Google TTS rate limits
            if i < len(chunks):
                time.sleep(self.CHUNK_DELAY)

        audio = b"".join(mp3_parts)
        logger.info("Synthesis complete: %d bytes total", len(audio))
        return audio

    def synthesize_to_file(self, text: str, output_path: Optional[str] = None) -> str:
        audio_bytes = self.synthesize(text)
        if output_path is None:
            os.makedirs(settings.TMP_DIR, exist_ok=True)
            output_path = os.path.join(settings.TMP_DIR, f"{uuid.uuid4().hex}.mp3")
        Path(output_path).write_bytes(audio_bytes)
        logger.info("Wrote MP3 to %s", output_path)
        return output_path

    # ── Retry logic ───────────────────────────────────────────────────────────

    def _gtts_chunk_with_retry(self, text: str, chunk_num: int, total: int) -> bytes:
        """
        Synthesise one chunk with exponential backoff on rate limit errors.
        Retries up to MAX_RETRIES times on 429 / connection errors.
        """
        delay = self.RETRY_DELAY

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return self._gtts_chunk(text)
            except TTSError as exc:
                error_str = str(exc).lower()

                # Check for rate limit (429) or connection errors
                is_rate_limit = "429" in error_str or "too many requests" in error_str
                is_conn_error = any(k in error_str for k in [
                    "connection", "timeout", "network", "failed to connect"
                ])

                if (is_rate_limit or is_conn_error) and attempt < self.MAX_RETRIES:
                    logger.warning(
                        "Chunk %d/%d attempt %d failed (%s). "
                        "Retrying in %ds…",
                        chunk_num, total, attempt,
                        "rate limit" if is_rate_limit else "connection error",
                        delay,
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise TTSError(
                        f"Text-to-speech generation failed. "
                        f"Detail: {exc}. "
                        f"Probable cause: {'Rate limit exceeded — try a shorter document or try again in a minute.' if is_rate_limit else 'Unknown'}"
                    ) from exc

        raise TTSError("Max retries exceeded for TTS chunk.")

    # ── Internals ─────────────────────────────────────────────────────────────

    def _chunk(self, text: str) -> Iterator[str]:
        """Split text into sentence-aware chunks under CHUNK_SIZE chars."""
        if len(text) <= self.CHUNK_SIZE:
            yield text
            return

        sentences = re.split(r"(?<=[.!?])\s+", text)
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 > self.CHUNK_SIZE:
                if buffer:
                    yield buffer.strip()
                    buffer = ""
                if len(sentence) > self.CHUNK_SIZE:
                    for sub in textwrap.wrap(sentence, self.CHUNK_SIZE):
                        yield sub
                else:
                    buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()

        if buffer.strip():
            yield buffer.strip()

    def _gtts_chunk(self, text: str) -> bytes:
        """Call gTTS for a single chunk and return raw MP3 bytes."""
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise TTSError("gTTS is not installed.") from exc

        try:
            tts = gTTS(text=text, lang=self.lang, slow=self.slow, tld=self.tld)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception as exc:
            raise TTSError(str(exc)) from exc
