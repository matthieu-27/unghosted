"""Pydantic wire models for applicant-profile endpoints (us-4 item 3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from unghosted.schemas.projects import StrictModel


class ProfileHighlightModel(StrictModel):
    """One highlight or style note with its server-assigned stable id."""

    id: str
    text: str = Field(min_length=1)


class ProfileContentUpdate(StrictModel):
    """PATCH body for a draft version. Fields absent or null keep their
    current value — the wire format has no null-means-clear case."""

    headline: str | None = None
    seeking: str | None = None
    highlights: list[ProfileHighlightModel] | None = None
    motivation: str | None = None
    style_notes: list[ProfileHighlightModel] | None = None
    availability: str | None = None


class ProfileVersionRead(BaseModel):
    version: int
    status: str
    headline: str | None
    seeking: str | None
    highlights: list[ProfileHighlightModel]
    motivation: str | None
    style_notes: list[ProfileHighlightModel]
    availability: str | None
    approved_at: str | None
    created_at: str
    updated_at: str


class ProfileRead(BaseModel):
    approved: ProfileVersionRead | None
    draft: ProfileVersionRead | None
    versions: list[ProfileVersionRead]
