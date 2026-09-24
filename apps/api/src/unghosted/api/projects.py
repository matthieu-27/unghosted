"""Project endpoints (routes per docs/naming-table.md)."""

from __future__ import annotations

import uuid

from litestar import Controller, delete, get, patch, post
from litestar.datastructures import State
from litestar.di import NamedDependency
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath, FromQuery
from litestar.status_codes import HTTP_204_NO_CONTENT

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.templates import Template, TemplateError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import (
    DocumentTypeRead,
    ProjectCreate,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
)
from unghosted.services.projects import (
    ProjectService,
    ProjectView,
    UnknownTemplateError,
)


def _not_found(project_id: str) -> NotFoundException:
    return NotFoundException(
        detail=f"project {project_id} not found", extra={"code": "not_found"}
    )


def _read(view: ProjectView, state: State) -> ProjectRead:
    templates: dict[str, Template] = state.templates
    template = templates[view.template_key]
    return ProjectRead(
        id=view.id,
        name=view.name,
        description=view.description,
        template_key=view.template_key,
        template_version=view.template_version,
        archived=view.archived,
        document_types=[
            DocumentTypeRead(key=d.key, label=d.label, model_eligible=d.model_eligible)
            for d in template.document_types
        ],
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


class ProjectController(Controller):
    path = "/projects"

    @get()
    async def list_projects(
        self,
        project_service: NamedDependency[ProjectService],
        current_user: NamedDependency[uuid.UUID],
        state: State,
        include_archived: FromQuery[bool] = False,
    ) -> ProjectList:
        views = await project_service.list(
            current_user, include_archived=include_archived
        )
        return ProjectList(data=[_read(v, state) for v in views])

    @post(status_code=201, dto=StrictPydanticDTO[ProjectCreate])
    async def create_project(
        self,
        data: ProjectCreate,
        project_service: NamedDependency[ProjectService],
        current_user: NamedDependency[uuid.UUID],
        state: State,
    ) -> ProjectRead:
        try:
            view = await project_service.create(
                owner=current_user,
                template_key=data.template_key,
                name=data.name.strip(),
                description=data.description,
                settings=data.settings,
            )
        except (UnknownTemplateError, TemplateError) as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "validation_failed"}
            ) from exc
        return _read(view, state)

    @get("/{project_id:uuid}")
    async def get_project(
        self,
        project_id: FromPath[uuid.UUID],
        project_service: NamedDependency[ProjectService],
        current_user: NamedDependency[uuid.UUID],
        state: State,
    ) -> ProjectRead:
        try:
            return _read(await project_service.get(project_id, current_user), state)
        except ProjectNotFoundError as exc:
            raise _not_found(str(project_id)) from exc

    @patch("/{project_id:uuid}", dto=StrictPydanticDTO[ProjectUpdate])
    async def update_project(
        self,
        project_id: FromPath[uuid.UUID],
        data: ProjectUpdate,
        project_service: NamedDependency[ProjectService],
        current_user: NamedDependency[uuid.UUID],
        state: State,
    ) -> ProjectRead:
        try:
            return _read(
                await project_service.update(
                    project_id,
                    current_user,
                    name=data.name,
                    description=data.description,
                    archived=data.archived,
                ),
                state,
            )
        except ProjectNotFoundError as exc:
            raise _not_found(str(project_id)) from exc

    @delete("/{project_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_project(
        self,
        project_id: FromPath[uuid.UUID],
        project_service: NamedDependency[ProjectService],
        current_user: NamedDependency[uuid.UUID],
    ) -> None:
        try:
            await project_service.delete(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise _not_found(str(project_id)) from exc
