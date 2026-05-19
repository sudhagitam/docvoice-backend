# DocVoice AI – Cloud Run Dockerfile with OCR support
FROM python:3.11-slim

# Install system dependencies including tesseract and poppler for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-hin \
    tesseract-ocr-ara \
    tesseract-ocr-rus \
    tesseract-ocr-chi-sim \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

ENV PORT=8080
ENV PYTHONPATH=/app
ENV TMP_DIR=/tmp/docvoice

RUN mkdir -p /tmp/docvoice

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2 --timeout-keep-alive 120
