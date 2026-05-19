"""
DocVoice AI – Document Extractor
Handles PDF and DOCX text extraction with automatic OCR fallback for scanned PDFs.
"""

import io
import logging
import re
from pathlib import Path

logger = logging.getLogger("docvoice.extractor")


class DocumentExtractor:
    """Extracts plain text from PDF and DOCX files."""

    SUPPORTED = {".pdf", ".docx"}

    def extract(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text from file_bytes.
        Automatically uses OCR for scanned PDFs.
        """
        from core.exceptions import (
            CorruptedFileError,
            EmptyDocumentError,
            UnsupportedFileTypeError,
        )

        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED:
            raise UnsupportedFileTypeError(ext)

        logger.info("Extracting '%s' (%d bytes)", filename, len(file_bytes))

        try:
            if ext == ".pdf":
                text = self._extract_pdf(file_bytes)
            else:
                text = self._extract_docx(file_bytes)
        except (UnsupportedFileTypeError, EmptyDocumentError, CorruptedFileError):
            raise
        except Exception as exc:
            logger.exception("Unexpected extraction error")
            raise CorruptedFileError(str(exc)) from exc

        text = self._clean(text)

        if not text.strip():
            raise EmptyDocumentError()

        logger.info("Extracted %d characters from '%s'", len(text), filename)
        return text

    # ── PDF ───────────────────────────────────────────────────────────────────

    def _extract_pdf(self, data: bytes) -> str:
        from core.exceptions import CorruptedFileError

        try:
            import PyPDF2
        except ImportError as exc:
            raise CorruptedFileError("PyPDF2 not installed") from exc

        try:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise CorruptedFileError(f"Cannot parse PDF: {exc}") from exc

        if reader.is_encrypted:
            raise CorruptedFileError("Password-protected PDFs are not supported.")

        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                logger.warning("Failed to extract page %d; skipping.", i + 1)

        text = "\n".join(parts)

        # Always try OCR if text is empty or very sparse (scanned PDF)
        total_pages = len(reader.pages)
        avg_chars = len(text.strip()) / max(total_pages, 1)

        if avg_chars < 50:  # Less than 50 chars per page = likely scanned
            logger.info(
                "Sparse text (%.0f chars/page avg) — running OCR on all pages",
                avg_chars,
            )
            ocr_text = self._ocr_pdf(data)
            if len(ocr_text.strip()) > len(text.strip()):
                logger.info("OCR produced better results: %d chars", len(ocr_text))
                text = ocr_text

        return text

    def _ocr_pdf(self, data: bytes) -> str:
        """OCR using pdf2image + pytesseract."""
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            from PIL import Image

            logger.info("Starting OCR on PDF (%d bytes)…", len(data))

            # Convert PDF pages to images
            images = convert_from_bytes(
                data,
                dpi=200,          # Good quality vs speed balance
                fmt="jpeg",
                thread_count=2,
            )

            logger.info("OCR: converted %d pages to images", len(images))

            parts = []
            for i, img in enumerate(images):
                logger.debug("OCR: processing page %d/%d", i + 1, len(images))
                page_text = pytesseract.image_to_string(img, lang="eng")
                parts.append(page_text)

            result = "\n".join(parts)
            logger.info("OCR complete: %d characters extracted", len(result))
            return result

        except ImportError as exc:
            logger.warning("OCR libraries not available: %s", exc)
            return ""
        except Exception as exc:
            logger.warning("OCR failed: %s", exc)
            return ""

    # ── DOCX ──────────────────────────────────────────────────────────────────

    def _extract_docx(self, data: bytes) -> str:
        from core.exceptions import CorruptedFileError

        try:
            from docx import Document
        except ImportError as exc:
            raise CorruptedFileError("python-docx not installed") from exc

        try:
            doc = Document(io.BytesIO(data))
        except Exception as exc:
            raise CorruptedFileError(f"Cannot parse DOCX: {exc}") from exc

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text)

        return "\n".join(paragraphs)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()
