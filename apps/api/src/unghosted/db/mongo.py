"""Async MongoDB client (PyMongo native async API — Motor is EOL)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pymongo import AsyncMongoClient

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase

    from unghosted.config import Settings


def create_mongo_client(settings: Settings) -> AsyncMongoClient[dict[str, object]]:
    """One client per process. The client is safe to share across tasks."""
    return AsyncMongoClient(settings.mongo_url, uuidRepresentation="standard")


def get_tracker_db(
    client: AsyncMongoClient[dict[str, object]], name: str
) -> AsyncDatabase[dict[str, object]]:
    return client.get_database(name)
