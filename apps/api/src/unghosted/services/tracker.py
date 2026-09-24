"""Tracker service: fetch + operation batches with revision guard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from unghosted.domain.operations import (
    apply_operations,
    op_from_dict,
)
from unghosted.repositories.projects import ProjectRepository
from unghosted.repositories.tracker import StaleRevisionError, TrackerRepository


@dataclass(frozen=True)
class TrackerState:
    definition: dict[str, Any]
    rows: list[dict[str, Any]]

    @property
    def revision(self) -> int:
        return int(self.definition["revision"])


@dataclass(frozen=True)
class AppliedResult:
    revision: int
    applied: list[dict[str, Any]]


class TrackerService:
    def __init__(self, projects: ProjectRepository, tracker: TrackerRepository) -> None:
        self._projects = projects
        self._tracker = tracker

    async def fetch(self, project_id: uuid.UUID, owner: uuid.UUID) -> TrackerState:
        await self._projects.get(project_id, owner)  # ownership gate
        definition = await self._tracker.get_definition(project_id)
        rows = await self._tracker.list_rows(project_id)
        return TrackerState(definition=definition, rows=rows)

    async def apply(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        base_revision: int,
        raw_operations: list[dict[str, Any]],
    ) -> AppliedResult:
        await self._projects.get(project_id, owner)
        definition = await self._tracker.get_definition(project_id)
        rows = await self._tracker.list_rows(project_id)

        # A stale base cannot be rebased server-side for arbitrary op lists:
        # reject and hand the client the current revision to rebase itself.
        if int(definition["revision"]) != base_revision:
            raise StaleRevisionError(int(definition["revision"]))

        operations = [op_from_dict(raw) for raw in raw_operations]
        # OperationError propagates: the controller maps it to 422.
        batch = apply_operations(definition["columns"], rows, operations)

        new_definition = {**definition, "columns": batch.columns}
        revision = await self._tracker.save_batch(
            project_id,
            expected_revision=base_revision,
            new_definition=new_definition,
            upserted_rows=[
                r for r in batch.rows if r["_id"] in set(batch.upserted_row_ids)
            ],
            deleted_row_ids=list(batch.deleted_row_ids),
            changed_rows=[
                r for r in batch.rows if r["_id"] in set(batch.changed_row_ids)
            ],
        )
        return AppliedResult(
            revision=revision,
            applied=[{"op": raw.get("op")} for raw in raw_operations],
        )
