"""Pydantic wire models for document endpoints (docs/api-contract.md)."""

from __future__ import annotations

from dataclasses import dataclass

from litestar.datastructures import UploadFile
from pydantic import BaseModel


@dataclass
class DocumentUploadForm:
    """Multipart body: the file plus the type key assigned at upload
    (us-4 item 1). Parsed by Litestar's multipart layer, not StrictPydanticDTO
    — UploadFile has no pydantic core schema, so a plain dataclass is the
    form boundary and the JSON models below stay strict. An empty or
    unknown type_key is rejected by the service (validate_type_key)."""

    file: UploadFile
    type_key: str


class DocumentRead(BaseModel):
    id: str
    type_key: str
    model_eligible: bool
    original_filename: str
    size_bytes: int
    created_at: str


class DocumentList(BaseModel):
    data: list[DocumentRead]
