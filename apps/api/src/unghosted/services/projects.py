"""Project service: CRUD + template instantiation (ADR 0006 write order)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from unghosted.domain.templates import TemplateError, instantiate_tracker
from unghosted.repositories.projects import ProjectRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unghosted.db.models import Project
    from unghosted.domain.templates import Template
    from unghosted.repositories.tracker import TrackerRepository


class UnknownTemplateError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(f"unknown template {key!r}")
        self.key = key


@dataclass(frozen=True)
class ProjectView:
    id: str
    name: str
    description: str | None
    template_key: str
    template_version: int
    archived: bool
    created_at: str
    updated_at: str


def _view(project: Project) -> ProjectView:
    return ProjectView(
        id=str(project.id),
        name=project.name,
        description=project.description,
        template_key=project.template_key,
        template_version=project.template_version,
        archived=project.archived_at is not None,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


class ProjectService:
    def __init__(
        self,
        projects: ProjectRepository,
        tracker: TrackerRepository,
        templates: dict[str, Template],
    ) -> None:
        self._projects = projects
        self._tracker = tracker
        self._templates = templates

    async def create(
        self,
        *,
        owner: uuid.UUID,
        template_key: str,
        name: str,
        description: str | None,
        settings: dict[str, Any],
    ) -> ProjectView:
        template = self._templates.get(template_key)
        if template is None:
            raise UnknownTemplateError(template_key)
        try:
            definition = instantiate_tracker(template, settings)
        except TemplateError as exc:
            raise TemplateError(str(exc)) from exc

        # Write order (ADR 0006): Postgres row first — it owns identity —
        # then the Mongo tracker definition. Failure at step 2 leaves a
        # project without a tracker, repaired by reseed/reconcile.
        project = await self._projects.create(
            owner=owner,
            name=name,
            description=description,
            template_key=template.key,
            template_version=template.version,
        )
        await self._tracker.create_tracker(project.id, definition)
        return _view(project)

    async def list(
        self, owner: uuid.UUID, *, include_archived: bool
    ) -> list[ProjectView]:
        projects: Sequence[Project] = await self._projects.list_for_owner(
            owner,
            include_archived=include_archived,
        )
        return [_view(p) for p in projects]

    async def get(self, project_id: uuid.UUID, owner: uuid.UUID) -> ProjectView:
        return _view(await self._projects.get(project_id, owner))

    async def update(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        name: str | None,
        description: str | None,
        archived: bool | None,
    ) -> ProjectView:
        return _view(
            await self._projects.update(
                project_id,
                owner,
                name=name,
                description=description,
                archived=archived,
            ),
        )

    async def delete(self, project_id: uuid.UUID, owner: uuid.UUID) -> None:
        # Soft delete now; purge of Mongo + storage is a post-MVP job (ADR 0006).
        await self._projects.soft_delete(project_id, owner)
