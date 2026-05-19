"""
DocVoice AI – FastAPI Backend for Google Cloud Run
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("docvoice")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.routes import router

app = FastAPI(
    title="DocVoice AI",
    description="Convert PDF / DOCX documents to speech",
    version="2.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/api/health")
async def health():
    # Check OCR availability
    ocr_available = False
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        pytesseract.get_tesseract_version()
        ocr_available = True
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "DocVoice AI",
        "version": "2.1.0",
        "platform": "Google Cloud Run",
        "ocr_enabled": ocr_available,
        "max_upload_mb": int(os.environ.get("MAX_UPLOAD_BYTES", 104857600)) // (1024*1024),
    }
