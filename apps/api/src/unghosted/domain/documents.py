"""Document upload rules (us-4 item 1). Pure domain.

PDF-only, capped size, type drawn from the project's template list.
Content is sniffed, never trusted from the filename or the browser's
content type.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unghosted.domain.templates import DocumentType, Template

MAX_DOCUMENT_BYTES = 3 * 1024 * 1024
"""3 MiB per file (us-4 item 1)."""

PDF_MAGIC = b"%PDF-"


class DocumentValidationError(ValueError):
    """Upload rejected: not a PDF, too large, or type outside the template."""


def validate_type_key(type_key: str, template: Template) -> DocumentType:
    """Resolve the upload type against the template list (ADR 0009 point 1)."""
    for doc_type in template.document_types:
        if doc_type.key == type_key:
            return doc_type
    raise DocumentValidationError(
        f"unknown document type {type_key!r} for template {template.key!r}"
    )


def sniff_pdf(content: bytes) -> None:
    """Reject anything whose header bytes are not a PDF signature."""
    if not content.startswith(PDF_MAGIC):
        raise DocumentValidationError("file is not a PDF")


def extract_pdf_text(content: bytes) -> str:
    """Full parse with pypdf: proves the payload is a readable PDF and
    returns its text. Raises DocumentValidationError on any parse failure,
    so a corrupt file can never produce a document_texts row."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) == 0:
            raise DocumentValidationError("PDF has no pages")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except DocumentValidationError:
        raise
    except (PdfReadError, ValueError, TypeError) as exc:
        raise DocumentValidationError(f"PDF cannot be parsed: {exc}") from exc


def checksum_sha256(content: bytes) -> str:
    """Plaintext checksum stored on the row for integrity comparison."""
    return hashlib.sha256(content).hexdigest()


def storage_key(owner_id: str, document_id: str) -> str:
    """Storage path per docs/diagrams/storage-layout.puml: the user-supplied
    filename never reaches storage."""
    return f"users/{owner_id}/documents/{document_id}.bin"


def parse_master_key(value: str) -> bytes:
    """Decode the configured master key; fail startup on a wrong-length key."""
    try:
        key = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("master key is not valid base64") from exc
    if len(key) != 32:
        raise ValueError(
            f"master key must decode to 32 bytes, got {len(key)}"
        ) from None
    return key
