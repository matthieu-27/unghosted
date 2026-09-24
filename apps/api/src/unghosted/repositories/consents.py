"""Consent persistence (PostgreSQL). One row per (user, kind); withdrawal
sets withdrawn_at (us-4 item 5: withdrawal honored, history kept)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.db.models import Consent

if TYPE_CHECKING:
    from collections.abc import Sequence


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Consent]:
        stmt = select(Consent).where(Consent.user_id == user_id)
        return (await self._session.scalars(stmt)).all()

    async def get(self, user_id: uuid.UUID, kind: str) -> Consent | None:
        stmt = select(Consent).where(Consent.user_id == user_id, Consent.kind == kind)
        return (await self._session.scalars(stmt)).first()

    async def has_active(self, user_id: uuid.UUID, kind: str) -> bool:
        consent = await self.get(user_id, kind)
        return consent is not None and consent.withdrawn_at is None

    async def grant(self, user_id: uuid.UUID, kind: str) -> Consent:
        """Grant or re-grant: a withdrawn row is reactivated with a fresh
        granted_at instead of duplicating (the unique constraint enforces
        one row per user and kind)."""
        consent = await self.get(user_id, kind)
        if consent is None:
            consent = Consent(user_id=user_id, kind=kind)
            self._session.add(consent)
        else:
            consent.granted_at = datetime.now(UTC)
            consent.withdrawn_at = None
        await self._session.flush()
        await self._session.refresh(consent)
        return consent

    async def withdraw(self, user_id: uuid.UUID, kind: str) -> None:
        await self._session.execute(
            update(Consent)
            .where(
                Consent.user_id == user_id,
                Consent.kind == kind,
                Consent.withdrawn_at.is_(None),
            )
            .values(withdrawn_at=datetime.now(UTC))
        )
