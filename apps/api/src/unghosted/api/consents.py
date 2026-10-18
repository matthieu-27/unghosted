"""Consent endpoints: grant, withdraw, list (us-4 item 5)."""

from __future__ import annotations

import uuid

from litestar import Controller, delete, get, post
from litestar.di import NamedDependency
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath
from litestar.status_codes import HTTP_204_NO_CONTENT

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.schemas import (
    CONSENT_KINDS,
    ConsentGrant,
    ConsentList,
    ConsentRead,
)
from unghosted.services.consents import ConsentNotFoundError, ConsentService


class ConsentController(Controller):
    path = "/account/consents"

    @get()
    async def list_consents(
        self,
        consent_service: NamedDependency[ConsentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ConsentList:
        views = await consent_service.list_for_user(current_user)
        return ConsentList(
            data=[
                ConsentRead(
                    kind=v.kind, granted_at=v.granted_at, withdrawn_at=v.withdrawn_at
                )
                for v in views
            ]
        )

    @post(status_code=201, dto=StrictPydanticDTO[ConsentGrant])
    async def grant_consent(
        self,
        data: ConsentGrant,
        consent_service: NamedDependency[ConsentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ConsentRead:
        view = await consent_service.grant(current_user, data.kind)
        return ConsentRead(
            kind=view.kind, granted_at=view.granted_at, withdrawn_at=None
        )

    @delete("/{kind: str}", status_code=HTTP_204_NO_CONTENT)
    async def withdraw_consent(
        self,
        kind: FromPath[str],
        consent_service: NamedDependency[ConsentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> None:
        if kind not in CONSENT_KINDS:
            raise ValidationException(
                detail=f"unknown consent kind {kind!r}",
                extra={"code": "validation_failed"},
            ) from None
        try:
            await consent_service.withdraw(current_user, kind)
        except ConsentNotFoundError as exc:
            raise NotFoundException(
                detail=f"no active consent {kind!r}",
                extra={"code": "not_found"},
            ) from exc
