"""
DocVoice AI – API Routes (Cloud Run)
Supports files up to 100 MB, Telugu OCR, 12 languages.
"""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from core.config import settings
from core.exceptions import DocVoiceError
from core.extractor import DocumentExtractor, TESSERACT_LANG_MAP
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
        "ocr_languages": list(TESSERACT_LANG_MAP.keys()),
    }


# ── Extract ───────────────────────────────────────────────────────────────────

@router.post("/extract")
async def extract_text(
    file: Annotated[UploadFile, File()],
    lang: Annotated[str, Form()] = "en",
):
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    logger.info("Extract: %s (%.1f MB) lang=%s", file.filename, size_mb, lang)

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is {size_mb:.1f} MB. Limit is "
                                 f"{settings.MAX_UPLOAD_BYTES // (1024*1024)} MB.")
    try:
        text = extractor.extract(file_bytes, file.filename or "upload", lang=lang)
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("Unexpected extract error")
        raise HTTPException(500, str(exc)) from exc

    preview = text[: settings.MAX_TEXT_CHARS]
    return {
        "filename": file.filename,
        "char_count": len(text),
        "truncated": len(text) > settings.MAX_TEXT_CHARS,
        "text": preview,
    }


# ── Synthesize ────────────────────────────────────────────────────────────────

@router.post("/synthesize")
async def synthesize(
    file: Annotated[UploadFile, File()],
    lang: Annotated[str, Form()] = "en",
    tld:  Annotated[str, Form()] = "com",
    slow: Annotated[bool, Form()] = False,
):
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    logger.info("Synthesize: %s (%.1f MB) lang=%s", file.filename, size_mb, lang)

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is {size_mb:.1f} MB. Limit is "
                                 f"{settings.MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    # Extract text (pass lang for OCR)
    try:
        text = extractor.extract(file_bytes, file.filename or "upload", lang=lang)
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("Extract error")
        raise HTTPException(500, f"Text extraction failed: {exc}") from exc

    text = text[: settings.MAX_TEXT_CHARS]

    # Synthesize audio
    try:
        engine = TTSEngine(lang=lang, slow=slow, tld=tld)
        mp3_bytes = engine.synthesize(text)
    except DocVoiceError as exc:
        return _err(exc)
    except Exception as exc:
        logger.exception("TTS error")
        raise HTTPException(500, f"TTS failed: {exc}") from exc

    base = os.path.splitext(file.filename or "document")[0]
    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{base}_audio.mp3"',
            "X-Char-Count": str(len(text)),
        },
    )


# ── Synthesize raw text ───────────────────────────────────────────────────────

@router.post("/synthesize-text")
async def synthesize_text(
    text: Annotated[str, Form()],
    lang: Annotated[str, Form()] = "en",
    tld:  Annotated[str, Form()] = "com",
    slow: Annotated[bool, Form()] = False,
):
    if not text.strip():
        raise HTTPException(422, "Text is empty.")
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
