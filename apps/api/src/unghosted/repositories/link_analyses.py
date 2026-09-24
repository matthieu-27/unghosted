"""Link-analysis persistence (PostgreSQL)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from unghosted.db.models import LinkAnalysis

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class LinkAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, analysis: LinkAnalysis) -> LinkAnalysis:
        self._session.add(analysis)
        await self._session.flush()
        await self._session.refresh(analysis)
        return analysis

    async def cached_for_source(
        self, project_id: uuid.UUID, source: str, *, max_age: timedelta
    ) -> LinkAnalysis | None:
        """Latest successful analysis for this exact source within the
        window (per-URL extraction cache, eco-design)."""
        stmt = (
            select(LinkAnalysis)
            .where(
                LinkAnalysis.project_id == project_id,
                LinkAnalysis.source == source,
                LinkAnalysis.status == "ok",
                LinkAnalysis.input_type == "url",
                LinkAnalysis.created_at >= datetime.now(UTC) - max_age,
            )
            .order_by(LinkAnalysis.created_at.desc())
            .limit(1)
        )
        result: Sequence[LinkAnalysis] = (await self._session.scalars(stmt)).all()
        return result[0] if result else None

    async def latest_for_source(
        self, project_id: uuid.UUID, source: str
    ) -> LinkAnalysis | None:
        """Latest successful URL analysis for this source, whatever its age.
        Mail drafting grounds on the stored listing text (us-5 items 2–3);
        unlike the extraction cache, relevance does not expire."""
        stmt = (
            select(LinkAnalysis)
            .where(
                LinkAnalysis.project_id == project_id,
                LinkAnalysis.source == source,
                LinkAnalysis.status == "ok",
                LinkAnalysis.input_type == "url",
            )
            .order_by(LinkAnalysis.created_at.desc())
            .limit(1)
        )
        result: Sequence[LinkAnalysis] = (await self._session.scalars(stmt)).all()
        return result[0] if result else None
