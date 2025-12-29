"""
Input validation & sanitization helpers.

- Pydantic-friendly helpers to sanitize and validate user text
- Lightweight XSS hardening (strip <script> tags, dangerous attributes)
- Simple toxic/inappropriate content filter (keyword based)
- Request body size limiting middleware to prevent DoS by huge payloads
"""

import logging
import os
import re
from typing import Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

# === Configurable limits (can be overridden via environment variables) ===

MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))
MAX_TASK_NAME_LENGTH: int = int(os.getenv("MAX_TASK_NAME_LENGTH", "255"))
MAX_COMMENT_LENGTH: int = int(os.getenv("MAX_COMMENT_LENGTH", "2000"))
MAX_SESSION_ID_LENGTH: int = int(os.getenv("MAX_SESSION_ID_LENGTH", "255"))

# Max raw HTTP request body size in bytes (default ~1MB)
MAX_REQUEST_SIZE_BYTES: int = int(os.getenv("MAX_REQUEST_SIZE_BYTES", "1048576"))

# Very small, explicit list of obviously inappropriate/toxic terms.
# This is intentionally simple and local – enough to block clearly bad input.
TOXIC_KEYWORDS = {
    "kill yourself",
    "kys",
    "fuck you",
    "ngu vcl",
    "đồ ngu",
    "racist",
    "hate speech",
}


def _strip_control_chars(text: str) -> str:
    """Remove non-printable control characters."""
    return "".join(ch for ch in text if ch.isprintable() or ch in ("\n", "\r", "\t"))


def sanitize_text(text: str) -> str:
    """
    Basic XSS-style sanitization:
    - Strip control characters
    - Remove <script>...</script> blocks
    - Remove on*="" event-handler attributes

    NOTE: Proper XSS prevention must still be done at the frontend render layer
    (e.g. escaping/encoding). This function just reduces obvious abuse.
    """
    if text is None:
        return text

    cleaned = _strip_control_chars(text)

    # Remove <script>...</script> blocks (case-insensitive, multiline)
    cleaned = re.sub(
        r"(?is)<script.*?>.*?</script>",
        "",
        cleaned,
    )

    # Remove inline event handlers like onclick="...", onerror='...'
    cleaned = re.sub(
        r'\son\w+\s*=\s*(".*?"|\'.*?\')',
        "",
        cleaned,
    )

    return cleaned.strip()


def is_toxic_or_inappropriate(text: str) -> bool:
    """Very lightweight toxic/inappropriate content detection."""
    if not text:
        return False

    lowered = text.lower()
    for keyword in TOXIC_KEYWORDS:
        if keyword in lowered:
            return True
    return False


def validate_and_sanitize_text(
    value: Optional[str],
    *,
    max_length: int,
    field_name: str,
    allow_empty: bool = False,
) -> Optional[str]:
    """
    Common helper used by Pydantic validators.

    - None is allowed (for optional fields)
    - Optionally reject empty strings
    - Enforce max_length (to prevent extremely large payloads)
    - Sanitize common XSS patterns
    - Block clearly toxic/inappropriate content
    """
    if value is None:
        return None

    value = value.strip()

    if not value and not allow_empty:
        raise ValueError(f"{field_name} must not be empty")

    if len(value) > max_length:
        raise ValueError(
            f"{field_name} is too long (max {max_length} characters)"
        )

    sanitized = sanitize_text(value)

    if is_toxic_or_inappropriate(sanitized):
        # Do not echo back original content in error messages.
        raise ValueError(
            f"{field_name} contains inappropriate or toxic content and was rejected"
        )

    return sanitized


class InputSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple middleware to limit raw HTTP request body size.

    This protects against extremely large payloads even before Pydantic parsing,
    complementing per-field max_length validation.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.max_size = MAX_REQUEST_SIZE_BYTES

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        # Only check methods that usually have a body
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > self.max_size:
                        logging.warning(
                            "Request rejected due to size limit: %s bytes > %s bytes",
                            size,
                            self.max_size,
                        )
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "detail": "Request body too large. Please reduce input size."
                            },
                        )
                except ValueError:
                    # If header is malformed, log and continue; body parsing will fail later if needed
                    logging.warning("Invalid Content-Length header: %r", content_length)

        return await call_next(request)


