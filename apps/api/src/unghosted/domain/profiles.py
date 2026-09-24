"""Applicant-profile domain types shared by the service and repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProfileContent:
    """Editable profile fields (us-4 item 3). A field that is None keeps
    the stored value: the wire contract is absent-or-null-means-keep, and
    the PATCH endpoint can never null a field out."""

    headline: str | None = None
    seeking: str | None = None
    highlights: list[dict[str, Any]] | None = None
    motivation: str | None = None
    style_notes: list[dict[str, Any]] | None = None
    availability: str | None = None
