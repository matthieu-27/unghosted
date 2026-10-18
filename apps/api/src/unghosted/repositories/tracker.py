"""Tracker persistence (MongoDB: tracker_definitions + tracker_rows)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pymongo import ReturnDocument

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase


class TrackerNotFoundError(LookupError):
    """No tracker definition for this project."""


class StaleRevisionError(Exception):
    """The definition moved on between read and write."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"current revision is {current_revision}")
        self.current_revision = current_revision


_INDEXES_ENSURED = False
"""Process-wide flag: create_index is idempotent, so racing first-callers
are safe. Lazy creation keeps app startup (and the health endpoint) free
of database round-trips (eco-design: no work without a request needing it)."""


class TrackerRepository:
    def __init__(self, db: AsyncDatabase[dict[str, Any]]) -> None:
        self._definitions: AsyncCollection[dict[str, Any]] = db.get_collection(
            "tracker_definitions"
        )
        self._rows: AsyncCollection[dict[str, Any]] = db.get_collection("tracker_rows")

    async def ensure_indexes(self) -> None:
        global _INDEXES_ENSURED
        if _INDEXES_ENSURED:
            return
        await self._definitions.create_index("project_id", unique=True)
        await self._rows.create_index([("project_id", 1), ("order_key", 1)])
        _INDEXES_ENSURED = True

    async def create_tracker(
        self, project_id: uuid.UUID, definition: dict[str, Any]
    ) -> None:
        await self.ensure_indexes()
        doc = {"_id": project_id, "project_id": project_id, **definition}
        await self._definitions.insert_one(doc)
        # No seed rows: an empty tracker is the honest starting state.

    async def get_definition(self, project_id: uuid.UUID) -> dict[str, Any]:
        doc = await self._definitions.find_one({"project_id": project_id})
        if doc is None:
            raise TrackerNotFoundError(str(project_id))
        return doc

    async def list_rows(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        cursor = self._rows.find({"project_id": project_id}).sort("order_key", 1)
        return [doc async for doc in cursor]

    async def cell_value_exists(
        self, project_id: uuid.UUID, column_key: str, value: Any
    ) -> bool:
        """Whether any row of this project holds this exact cell value.
        Used by link analysis for the duplicate-URL warning (us-3 item 5)."""
        count = await self._rows.count_documents(
            {"project_id": project_id, f"cells.{column_key}": value}, limit=1
        )
        return count > 0

    async def save_batch(
        self,
        project_id: uuid.UUID,
        *,
        expected_revision: int,
        new_definition: dict[str, Any],
        upserted_rows: list[dict[str, Any]],
        deleted_row_ids: list[str],
        changed_rows: list[dict[str, Any]],
    ) -> int:
        """Persist one applied operation batch and bump the revision.

        Single-node Mongo (dev compose) has no multi-document transactions,
        so the definition revision is the guard: rows are written first, and
        the definition replace fails on revision mismatch — the loser's row
        writes are then overwritten by the winner's next batch or reconciled
        (ADR 0006). Postgres stays the system of record for ownership.
        """
        for row in upserted_rows:
            await self._rows.update_one(
                {"_id": row["_id"]},
                {
                    "$set": {
                        "project_id": project_id,
                        "order_key": row["order_key"],
                        "cells": row["cells"],
                    }
                },
                upsert=True,
            )
        for row in changed_rows:
            await self._rows.update_one(
                {"_id": row["_id"], "project_id": project_id},
                {"$set": {"cells": row["cells"]}},
            )
        if deleted_row_ids:
            await self._rows.delete_many(
                {"_id": {"$in": deleted_row_ids}, "project_id": project_id}
            )

        result = await self._definitions.find_one_and_update(
            {"project_id": project_id, "revision": expected_revision},
            {"$set": {**new_definition, "revision": expected_revision + 1}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            current = await self._definitions.find_one(
                {"project_id": project_id}, {"revision": 1}
            )
            raise StaleRevisionError(
                current["revision"] if current else expected_revision
            )
        return int(result["revision"])
