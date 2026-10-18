"""Project persistence (PostgreSQL)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.db.models import Project

if TYPE_CHECKING:
    from collections.abc import Sequence


class ProjectNotFoundError(LookupError):
    """No live project with this id owned by this user."""


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_owner(
        self, owner: uuid.UUID, *, include_archived: bool
    ) -> Sequence[Project]:
        stmt = select(Project).where(
            Project.owner_user_id == owner, Project.deleted_at.is_(None)
        )
        if not include_archived:
            stmt = stmt.where(Project.archived_at.is_(None))
        stmt = stmt.order_by(Project.updated_at.desc())
        return (await self._session.scalars(stmt)).all()

    async def get(self, project_id: uuid.UUID, owner: uuid.UUID) -> Project:
        project = await self._session.get(Project, project_id)
        if (
            project is None
            or project.deleted_at is not None
            or project.owner_user_id != owner
        ):
            raise ProjectNotFoundError(str(project_id))
        return project

    async def create(
        self,
        *,
        owner: uuid.UUID,
        name: str,
        description: str | None,
        template_key: str,
        template_version: int,
    ) -> Project:
        project = Project(
            owner_user_id=owner,
            name=name,
            description=description,
            template_key=template_key,
            template_version=template_version,
        )
        self._session.add(project)
        await self._session.flush()
        # onupdate expires timestamps: reload them inside the async context,
        # _view reads them after the session-scoped transaction ends.
        await self._session.refresh(project)
        return project

    async def update(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        archived: bool | None = None,
    ) -> Project:
        project = await self.get(project_id, owner)
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if archived is not None:
            project.archived_at = datetime.now(UTC) if archived else None
        await self._session.flush()
        await self._session.refresh(project)
        return project

    async def soft_delete(self, project_id: uuid.UUID, owner: uuid.UUID) -> None:
        await self.get(project_id, owner)
        await self._session.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(deleted_at=datetime.now(UTC)),
        )
