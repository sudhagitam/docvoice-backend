"""DocVoice AI – Domain Exceptions"""


class DocVoiceError(Exception):
    """Base exception for all DocVoice errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnsupportedFileTypeError(DocVoiceError):
    def __init__(self, ext: str):
        super().__init__(f"Unsupported file type: '{ext}'. Upload a PDF or DOCX.", 415)


class EmptyDocumentError(DocVoiceError):
    def __init__(self):
        super().__init__("The document contains no extractable text.", 422)


class CorruptedFileError(DocVoiceError):
    def __init__(self, detail: str = ""):
        msg = "The file appears to be corrupted or unreadable."
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(msg, 422)


class DocumentTooLargeError(DocVoiceError):
    def __init__(self, limit_chars: int):
        super().__init__(
            f"Document exceeds the {limit_chars:,}-character limit. "
            "Try a shorter document or split it into sections.",
            413,
        )


class TTSError(DocVoiceError):
    def __init__(self, detail: str = ""):
        msg = "Text-to-speech generation failed."
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(msg, 500)
