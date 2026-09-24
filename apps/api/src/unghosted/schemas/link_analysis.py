"""Pydantic models for the link-analysis endpoint (docs/api-contract.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from unghosted.schemas.projects import StrictModel


class LinkAnalysisBody(StrictModel):
    input: str = Field(min_length=1)
    force_kind: str | None = None


class ExtractedFieldModel(BaseModel):
    column_key: str
    value: Any
    provenance: str


class AnalysisWarningModel(BaseModel):
    code: str
    detail: str


class LinkAnalysisResult(StrictModel):
    page_kind: str | None
    page_kind_confidence: str | None
    page_kind_basis: str | None
    provider: str | None
    cached: bool
    fields: list[ExtractedFieldModel]
    warnings: list[AnalysisWarningModel]
