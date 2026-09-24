"""Document and document-text persistence (PostgreSQL)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.db.models import Document, DocumentText

if TYPE_CHECKING:
    from collections.abc import Sequence


class DocumentNotFoundError(LookupError):
    """No document with this id in this project."""


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        type_key: str,
        model_eligible: bool,
        storage_key: str,
        encrypted_data_key: bytes,
        key_algorithm_version: str,
        size_bytes: int,
        checksum_sha256: str,
        original_filename: str,
    ) -> Document:
        document = Document(
            id=document_id,
            project_id=project_id,
            type_key=type_key,
            model_eligible=model_eligible,
            storage_key=storage_key,
            encrypted_data_key=encrypted_data_key,
            key_algorithm_version=key_algorithm_version,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            original_filename=original_filename,
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[Document]:
        stmt = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
        return (await self._session.scalars(stmt)).all()

    async def latest_for_type(
        self, project_id: uuid.UUID, type_key: str
    ) -> Document | None:
        """Most recent document of one type — 'latest' is the query's own
        order, never a caller's assumption about list_for_project."""
        stmt = (
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.type_key == type_key,
            )
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        return (await self._session.scalars(stmt)).first()

    async def get(self, document_id: uuid.UUID, project_id: uuid.UUID) -> Document:
        document = await self._session.get(Document, document_id)
        if document is None or document.project_id != project_id:
            raise DocumentNotFoundError(str(document_id))
        return document

    async def delete(self, document_id: uuid.UUID) -> None:
        await self._session.execute(delete(Document).where(Document.id == document_id))


class DocumentTextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document_id: uuid.UUID, text: str) -> DocumentText:
        row = DocumentText(document_id=document_id, text=text)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_for_document(self, document_id: uuid.UUID) -> DocumentText | None:
        stmt = select(DocumentText).where(DocumentText.document_id == document_id)
        return (await self._session.scalars(stmt)).first()

    async def list_eligible_for_project(
        self, project_id: uuid.UUID
    ) -> Sequence[tuple[DocumentText, Document]]:
        """Texts of model-eligible documents only (ADR 0009 point 2):
        an ineligible upload never produces a document_texts row in the
        first place, and this query is the second barrier."""
        stmt = (
            select(DocumentText, Document)
            .join(Document, DocumentText.document_id == Document.id)
            .where(Document.project_id == project_id)
            .where(Document.model_eligible.is_(True))
            .order_by(Document.created_at)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def delete_for_document(self, document_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(DocumentText).where(DocumentText.document_id == document_id)
        )
