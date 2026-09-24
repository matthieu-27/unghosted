"""Applicant-profile persistence (PostgreSQL). One row per version (us-4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.db.models import ApplicantProfile
from unghosted.domain.profiles import ProfileContent

if TYPE_CHECKING:
    from collections.abc import Sequence


class ProfileVersionNotFoundError(LookupError):
    """No profile version with this number in this project."""


class ApplicantProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_project(
        self, project_id: uuid.UUID
    ) -> Sequence[ApplicantProfile]:
        stmt = (
            select(ApplicantProfile)
            .where(ApplicantProfile.project_id == project_id)
            .order_by(ApplicantProfile.version_number)
        )
        return (await self._session.scalars(stmt)).all()

    async def get(self, project_id: uuid.UUID, version_number: int) -> ApplicantProfile:
        stmt = select(ApplicantProfile).where(
            ApplicantProfile.project_id == project_id,
            ApplicantProfile.version_number == version_number,
        )
        profile = (await self._session.scalars(stmt)).first()
        if profile is None:
            raise ProfileVersionNotFoundError(str(version_number))
        return profile

    async def next_version_number(self, project_id: uuid.UUID) -> int:
        stmt = select(func.max(ApplicantProfile.version_number)).where(
            ApplicantProfile.project_id == project_id
        )
        current = (await self._session.scalars(stmt)).first() or 0
        return int(current) + 1

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        version_number: int,
        headline: str | None,
        seeking: str | None,
        highlights: list[dict[str, Any]],
        motivation: str | None,
        style_notes: list[dict[str, Any]],
        availability: str | None,
    ) -> ApplicantProfile:
        profile = ApplicantProfile(
            project_id=project_id,
            version_number=version_number,
            status="draft",
            headline=headline,
            seeking=seeking,
            highlights=highlights,
            motivation=motivation,
            style_notes=style_notes,
            availability=availability,
        )
        self._session.add(profile)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def update_fields(
        self, profile: ApplicantProfile, content: ProfileContent
    ) -> ApplicantProfile:
        if content.headline is not None:
            profile.headline = content.headline
        if content.seeking is not None:
            profile.seeking = content.seeking
        if content.highlights is not None:
            profile.highlights = content.highlights
        if content.motivation is not None:
            profile.motivation = content.motivation
        if content.style_notes is not None:
            profile.style_notes = content.style_notes
        if content.availability is not None:
            profile.availability = content.availability
        await self._session.flush()
        # onupdate expires timestamps: reload inside the async context.
        await self._session.refresh(profile)
        return profile

    async def approve(self, profile: ApplicantProfile) -> ApplicantProfile:
        """Mark this version approved, supersede any previous one. Never
        touches other drafts (us-4 item 3)."""
        await self._session.execute(
            update(ApplicantProfile)
            .where(
                ApplicantProfile.project_id == profile.project_id,
                ApplicantProfile.status == "approved",
            )
            .values(status="superseded")
        )
        profile.status = "approved"
        profile.approved_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def get_approved(self, project_id: uuid.UUID) -> ApplicantProfile | None:
        stmt = select(ApplicantProfile).where(
            ApplicantProfile.project_id == project_id,
            ApplicantProfile.status == "approved",
        )
        return (await self._session.scalars(stmt)).first()
