"""
DocVoice AI – TTS Engine
Converts text to MP3 using gTTS with chunking support for large documents.
"""

import io
import logging
import os
import textwrap
import uuid
from typing import Iterator, Optional
from pathlib import Path

from core.config import settings
from core.exceptions import TTSError

logger = logging.getLogger("docvoice.tts")

# Supported languages exposed to the frontend
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
    "zh": "Chinese (Mandarin)",
    "ar": "Arabic",
    "ru": "Russian",
}

# gTTS TLD → accent mapping (English only)
ENGLISH_ACCENTS: dict[str, str] = {
    "com": "US English",
    "co.uk": "UK English",
    "com.au": "Australian English",
    "co.in": "Indian English",
    "ca": "Canadian English",
}


class TTSEngine:
    """
    Converts plain text to MP3 audio using gTTS.

    Supports:
    - Multiple languages
    - Slow/normal speed
    - Chunked synthesis for large texts (avoids gTTS request-size limits)
    - In-memory concatenation (no pydub needed for simple concat)
    """

    CHUNK_SIZE = 4_000  # characters per gTTS request

    def __init__(self, lang: str = "en", slow: bool = False, tld: str = "com"):
        self.lang = lang if lang in SUPPORTED_LANGUAGES else "en"
        self.slow = slow
        self.tld = tld

    # ── Public API ────────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> bytes:
        """
        Convert *text* to MP3 bytes.

        Chunks long text, synthesises each chunk, and concatenates raw MP3
        frames (valid for gTTS output which uses MPEG frames).

        Args:
            text: Plain text to convert.

        Returns:
            MP3 audio as bytes.

        Raises:
            TTSError on synthesis failure.
        """
        if not text.strip():
            raise TTSError("Empty text passed to TTS engine.")

        chunks = list(self._chunk(text))
        logger.info(
            "Synthesising %d chunk(s), lang=%s, slow=%s", len(chunks), self.lang, self.slow
        )

        mp3_parts: list[bytes] = []
        for i, chunk in enumerate(chunks, 1):
            logger.debug("Processing chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
            mp3_parts.append(self._gtts_chunk(chunk))

        audio = b"".join(mp3_parts)
        logger.info("Synthesis complete: %d bytes", len(audio))
        return audio

    def synthesize_to_file(self, text: str, output_path: Optional[str] = None) -> str:
        """
        Synthesise *text* and write to a temp file.

        Returns:
            Absolute path to the generated MP3 file.
        """
        audio_bytes = self.synthesize(text)

        if output_path is None:
            os.makedirs(settings.TMP_DIR, exist_ok=True)
            output_path = os.path.join(settings.TMP_DIR, f"{uuid.uuid4().hex}.mp3")

        Path(output_path).write_bytes(audio_bytes)
        logger.info("Wrote MP3 to %s", output_path)
        return output_path

    # ── Internals ─────────────────────────────────────────────────────────────

    def _chunk(self, text: str) -> Iterator[str]:
        """Split text into sentence-aware chunks under CHUNK_SIZE chars."""
        if len(text) <= self.CHUNK_SIZE:
            yield text
            return

        # Split on sentence boundaries first
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 > self.CHUNK_SIZE:
                if buffer:
                    yield buffer.strip()
                    buffer = ""
                # Sentence itself is too long → hard-wrap
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
            logger.exception("gTTS synthesis failed")
            raise TTSError(str(exc)) from exc


