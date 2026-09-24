"""Consent service: grant, withdraw, list (us-4 item 5).

Mailbox-provider consents land here post-MVP; the kind is validated at
the schema layer (Literal), so no unknown kind ever reaches persistence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unghosted.db.models import Consent
    from unghosted.repositories.consents import ConsentRepository

MODEL_PROCESSING_CONSENT = "model_processing"
"""The consent kind covering model processing of documents (us-4 item 5)."""


class ConsentRequiredError(PermissionError):
    """Model-processing consent is missing or withdrawn. The operation that
    would prepare or send content to the model is refused, not degraded."""


class ConsentNotFoundError(LookupError):
    """No active consent of this kind to withdraw."""


async def require_model_consent(
    consents: ConsentRepository, user_id: uuid.UUID, action: str
) -> None:
    """The one consent gate both document upload and profile drafting pass
    through, so the refusal can never drift between the two flows."""
    if not await consents.has_active(user_id, MODEL_PROCESSING_CONSENT):
        raise ConsentRequiredError(f"model-processing consent is required to {action}")


@dataclass(frozen=True)
class ConsentView:
    kind: str
    granted_at: str
    withdrawn_at: str | None


class ConsentService:
    def __init__(self, consents: ConsentRepository) -> None:
        self._consents = consents

    async def list_for_user(self, user: uuid.UUID) -> list[ConsentView]:
        rows: Sequence[Consent] = await self._consents.list_for_user(user)
        return [
            ConsentView(
                kind=row.kind,
                granted_at=row.granted_at.isoformat(),
                withdrawn_at=row.withdrawn_at.isoformat()
                if row.withdrawn_at is not None
                else None,
            )
            for row in rows
        ]

    async def grant(self, user: uuid.UUID, kind: str) -> ConsentView:
        row = await self._consents.grant(user, kind)
        return ConsentView(
            kind=row.kind,
            granted_at=row.granted_at.isoformat(),
            withdrawn_at=None,
        )

    async def withdraw(self, user: uuid.UUID, kind: str) -> None:
        if not await self._consents.has_active(user, kind):
            raise ConsentNotFoundError(kind)
        await self._consents.withdraw(user, kind)
