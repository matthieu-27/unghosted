"""Pydantic wire models for consent endpoints (us-4 item 5)."""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel

from unghosted.schemas.projects import StrictModel

ConsentKind = Literal["model_processing"]
"""Kinds that can be granted today. Mailbox providers join post-MVP; this
Literal is the single place to extend."""

CONSENT_KINDS: tuple[str, ...] = get_args(ConsentKind)


class ConsentGrant(StrictModel):
    kind: ConsentKind


class ConsentRead(BaseModel):
    kind: str
    granted_at: str
    withdrawn_at: str | None


class ConsentList(BaseModel):
    data: list[ConsentRead]
