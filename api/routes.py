"""
DocVoice AI – API Routes (Cloud Run)
Supports files up to 100 MB with extended timeouts.
"""

import logging
import os
import traceback
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from core.config import settings
from core.exceptions import DocVoiceError
from core.extractor import DocumentExtractor
from core.tts_engine import ENGLISH_ACCENTS, SUPPORTED_LANGUAGES, TTSEngine

logger = logging.getLogger("docvoice.routes")
router = APIRouter()
extractor = DocumentExtractor()


def _err(exc: DocVoiceError) -> JSONResponse:
    logger.warning("DocVoiceError [%d]: %s", exc.status_code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# ── Languages ─────────────────────────────────────────────────────────────────

@router.get("/languages")
async def list_languages():
    return {
        "languages": SUPPORTED_LANGUAGES,
        "english_accents": ENGLISH_ACCENTS,
    }


# ── Extract ───────────────────────────────────────────────────────────────────

@router.post("/extract")
async def extract_text(file: Annotated[UploadFile, File()]):
    """Extract text from PDF or DOCX – no audio generated."""
    file_bytes = await file.read()

    size_mb = len(file_bytes) / (1024 * 1024)
    logger.info("Extract request: %s (%.1f MB)", file.filename, size_mb)

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"File is {size_mb:.1f} MB. Limit is "
            f"{settings.MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    try:
        text = extractor.extract(file_bytes, file.filename or "upload")
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("Unexpected extract error")
        raise HTTPException(500, f"Extract failed: {exc}") from exc

    preview = text[: settings.MAX_TEXT_CHARS]
    truncated = len(text) > settings.MAX_TEXT_CHARS

    return {
        "filename": file.filename,
        "char_count": len(text),
        "truncated": truncated,
        "text": preview,
    }


# ── Synthesize (file upload) ──────────────────────────────────────────────────

@router.post("/synthesize")
async def synthesize(
    file: Annotated[UploadFile, File()],
    lang: Annotated[str, Form()] = "en",
    tld:  Annotated[str, Form()] = "com",
    slow: Annotated[bool, Form()] = False,
):
    """
    Upload PDF/DOCX → receive MP3.
    Supports files up to 100 MB on Cloud Run.
    """
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    logger.info("Synthesize request: %s (%.1f MB) lang=%s", file.filename, size_mb, lang)

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"File is {size_mb:.1f} MB. Limit is "
            f"{settings.MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    # 1. Extract text
    try:
        text = extractor.extract(file_bytes, file.filename or "upload")
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("Extract error")
        raise HTTPException(500, f"Text extraction failed: {exc}") from exc

    # 2. Truncate if needed
    if len(text) > settings.MAX_TEXT_CHARS:
        logger.info(
            "Truncating text: %d → %d chars", len(text), settings.MAX_TEXT_CHARS
        )
        text = text[: settings.MAX_TEXT_CHARS]

    # 3. Synthesize
    try:
        engine = TTSEngine(lang=lang, slow=slow, tld=tld)
        mp3_bytes = engine.synthesize(text)
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("TTS error")
        raise HTTPException(500, f"TTS failed: {exc}") from exc

    base = os.path.splitext(file.filename or "document")[0]
    logger.info("Returning MP3: %d bytes", len(mp3_bytes))

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{base}_audio.mp3"',
            "X-Char-Count": str(len(text)),
        },
    )


# ── Synthesize (raw text) ─────────────────────────────────────────────────────

@router.post("/synthesize-text")
async def synthesize_text(
    text: Annotated[str, Form()],
    lang: Annotated[str, Form()] = "en",
    tld:  Annotated[str, Form()] = "com",
    slow: Annotated[bool, Form()] = False,
):
    """Convert raw text to MP3 (no file upload)."""
    if not text.strip():
        raise HTTPException(422, "Text cannot be empty.")

    text = text[: settings.MAX_TEXT_CHARS]

    try:
        engine = TTSEngine(lang=lang, slow=slow, tld=tld)
        mp3_bytes = engine.synthesize(text)
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("TTS error")
        raise HTTPException(500, f"TTS failed: {exc}") from exc

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="preview.mp3"'},
    )
