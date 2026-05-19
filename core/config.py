"""DocVoice AI – Config for Cloud Run (plain os.environ)"""
import os


class Settings:
    # Upload limits – Cloud Run supports large files
    MAX_UPLOAD_BYTES: int = int(os.environ.get("MAX_UPLOAD_BYTES", 100 * 1024 * 1024))  # 100 MB
    MAX_TEXT_CHARS: int   = int(os.environ.get("MAX_TEXT_CHARS", 200_000))               # ~2.5 hrs speech

    # TTS
    DEFAULT_LANG: str = os.environ.get("DEFAULT_LANG", "en")

    # Temp dir (/tmp is always writable on Cloud Run)
    TMP_DIR: str = os.environ.get("TMP_DIR", "/tmp/docvoice")

    # CORS
    ALLOWED_ORIGINS: list[str] = os.environ.get(
        "ALLOWED_ORIGINS", "*"
    ).split(",")


settings = Settings()
