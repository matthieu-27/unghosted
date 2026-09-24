"""Applicant-profile endpoints: state, draft, edit, approve (us-4 item 3)."""

from __future__ import annotations

import uuid

from litestar import Controller, get, patch, post
from litestar.di import NamedDependency
from litestar.exceptions import (
    HTTPException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.params import FromPath
from litestar.status_codes import (
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.profiles import ProfileContent
from unghosted.gateways.model import ModelUnavailableError
from unghosted.repositories.profiles import ProfileVersionNotFoundError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import (
    ProfileContentUpdate,
    ProfileHighlightModel,
    ProfileRead,
    ProfileVersionRead,
)
from unghosted.services.consents import ConsentRequiredError
from unghosted.services.profiles import (
    NoEligibleDocumentsError,
    ProfileNotEditableError,
    ProfileService,
    ProfileState,
    ProfileVersionView,
)


def _version_read(view: ProfileVersionView) -> ProfileVersionRead:
    return ProfileVersionRead(
        version=view.version,
        status=view.status,
        headline=view.headline,
        seeking=view.seeking,
        highlights=[ProfileHighlightModel.model_validate(h) for h in view.highlights],
        motivation=view.motivation,
        style_notes=[ProfileHighlightModel.model_validate(s) for s in view.style_notes],
        availability=view.availability,
        approved_at=view.approved_at,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _profile_read(state: ProfileState) -> ProfileRead:
    return ProfileRead(
        approved=_version_read(state.approved) if state.approved else None,
        draft=_version_read(state.draft) if state.draft else None,
        versions=[_version_read(v) for v in state.versions],
    )


class ProfileController(Controller):
    path = "/projects/{project_id:uuid}/profile"

    @get()
    async def get_profile(
        self,
        project_id: FromPath[uuid.UUID],
        profile_service: NamedDependency[ProfileService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ProfileRead:
        try:
            state = await profile_service.state(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        return _profile_read(state)

    @post("/drafts", status_code=200)
    async def draft_profile(
        self,
        project_id: FromPath[uuid.UUID],
        profile_service: NamedDependency[ProfileService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ProfileVersionRead:
        try:
            view = await profile_service.draft(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except ConsentRequiredError as exc:
            raise PermissionDeniedException(
                detail=str(exc), extra={"code": "consent_required"}
            ) from exc
        except NoEligibleDocumentsError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "no_eligible_documents"}
            ) from exc
        except ModelUnavailableError as exc:
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                extra={"code": "model_unavailable"},
            ) from exc
        return _version_read(view)

    @patch("/versions/{version:int}", dto=StrictPydanticDTO[ProfileContentUpdate])
    async def edit_profile(
        self,
        project_id: FromPath[uuid.UUID],
        version: FromPath[int],
        data: ProfileContentUpdate,
        profile_service: NamedDependency[ProfileService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ProfileVersionRead:
        try:
            view = await profile_service.edit(
                project_id,
                current_user,
                version,
                ProfileContent(
                    headline=data.headline,
                    seeking=data.seeking,
                    highlights=[h.model_dump() for h in data.highlights]
                    if data.highlights is not None
                    else None,
                    motivation=data.motivation,
                    style_notes=[s.model_dump() for s in data.style_notes]
                    if data.style_notes is not None
                    else None,
                    availability=data.availability,
                ),
            )
        except (ProjectNotFoundError, ProfileVersionNotFoundError) as exc:
            raise NotFoundException(
                detail=str(exc), extra={"code": "not_found"}
            ) from exc
        except ProfileNotEditableError as exc:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail=str(exc),
                extra={"code": "version_not_editable"},
            ) from exc
        return _version_read(view)

    @post("/versions/{version:int}/approve", status_code=200)
    async def approve_profile(
        self,
        project_id: FromPath[uuid.UUID],
        version: FromPath[int],
        profile_service: NamedDependency[ProfileService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ProfileVersionRead:
        try:
            view = await profile_service.approve(project_id, current_user, version)
        except (ProjectNotFoundError, ProfileVersionNotFoundError) as exc:
            raise NotFoundException(
                detail=str(exc), extra={"code": "not_found"}
            ) from exc
        except ProfileNotEditableError as exc:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail=str(exc),
                extra={"code": "version_not_editable"},
            ) from exc
        return _version_read(view)
