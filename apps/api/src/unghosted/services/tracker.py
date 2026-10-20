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
from unghosted.services.contacts import ContactLinkIndexer, contact_link_column_keys


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
    def __init__(
        self,
        projects: ProjectRepository,
        tracker: TrackerRepository,
        links: ContactLinkIndexer,
    ) -> None:
        self._projects = projects
        self._tracker = tracker
        self._links = links

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

        upserted_rows = [
            r for r in batch.rows if r["_id"] in set(batch.upserted_row_ids)
        ]
        changed_rows = [r for r in batch.rows if r["_id"] in set(batch.changed_row_ids)]
        deleted_row_ids = list(batch.deleted_row_ids)

        # Contact ids are checked before anything is written: an unknown id
        # is a 422, never a cell that outlives its contact.
        column_keys = contact_link_column_keys(definition)
        await self._links.validate(
            project_id,
            column_keys=column_keys,
            rows=[*upserted_rows, *changed_rows],
        )

        new_definition = {**definition, "columns": batch.columns}
        revision = await self._tracker.save_batch(
            project_id,
            expected_revision=base_revision,
            new_definition=new_definition,
            upserted_rows=upserted_rows,
            deleted_row_ids=deleted_row_ids,
            changed_rows=changed_rows,
        )
        # After the Mongo commit. The sync failure propagates so the request
        # fails loudly and the client retries the idempotent batch, instead
        # of a 2xx with a silently stale link index.
        await self._links.sync(
            project_id,
            column_keys=column_keys,
            rows=[*upserted_rows, *changed_rows],
            deleted_row_ids=deleted_row_ids,
        )
        return AppliedResult(
            revision=revision,
            applied=[{"op": raw.get("op")} for raw in raw_operations],
        )
