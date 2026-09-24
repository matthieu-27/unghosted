"""Document service: upload, list, delete, download (us-4 items 1, 2, 4).

Ownership flows through ProjectRepository.get: every operation resolves
the project for the seeded owner first, so a document id from another
project is indistinguishable from a missing one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from unghosted.domain.documents import (
    MAX_DOCUMENT_BYTES,
    DocumentValidationError,
    checksum_sha256,
    extract_pdf_text,
    sniff_pdf,
    validate_type_key,
)
from unghosted.domain.documents import (
    storage_key as build_storage_key,
)
from unghosted.gateways.encrypt import ALGORITHM_VERSION
from unghosted.services.consents import require_model_consent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unghosted.db.models import Document
    from unghosted.domain.templates import DocumentType, Template
    from unghosted.gateways.encrypt import EnvelopeEncryptor
    from unghosted.gateways.storage import StorageGateway
    from unghosted.repositories.consents import ConsentRepository
    from unghosted.repositories.documents import (
        DocumentRepository,
        DocumentTextRepository,
    )
    from unghosted.repositories.projects import ProjectRepository


@dataclass(frozen=True)
class DocumentView:
    id: str
    type_key: str
    model_eligible: bool
    original_filename: str
    size_bytes: int
    created_at: str


@dataclass(frozen=True)
class DownloadedDocument:
    original_filename: str
    content: bytes


def _view(document: Document) -> DocumentView:
    return DocumentView(
        id=str(document.id),
        type_key=document.type_key,
        model_eligible=document.model_eligible,
        original_filename=document.original_filename,
        size_bytes=document.size_bytes,
        created_at=document.created_at.isoformat(),
    )


async def store_document(
    *,
    documents: DocumentRepository,
    texts: DocumentTextRepository,
    storage: StorageGateway,
    encryptor: EnvelopeEncryptor,
    project_id: uuid.UUID,
    owner: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: DocumentType,
    filename: str,
    content: bytes,
    text: str | None,
) -> Document:
    """The one write path for stored PDFs — upload and letter approval
    share it so a new writer cannot drift from the ADR 0006 order: the
    Postgres row owns identity, the storage object follows, the derived
    text row last. The caller picks the id: filenames embed it."""
    encrypted_content, encrypted_data_key = encryptor.encrypt(content)
    document = await documents.create(
        project_id=project_id,
        document_id=document_id,
        type_key=doc_type.key,
        model_eligible=doc_type.model_eligible,
        storage_key=build_storage_key(str(owner), str(document_id)),
        encrypted_data_key=encrypted_data_key,
        key_algorithm_version=ALGORITHM_VERSION,
        size_bytes=len(content),
        checksum_sha256=checksum_sha256(content),
        original_filename=filename,
    )
    await storage.write(document.storage_key, encrypted_content)
    if doc_type.model_eligible and text is not None:
        await texts.create(document_id, text)
    return document


class DocumentService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        documents: DocumentRepository,
        texts: DocumentTextRepository,
        storage: StorageGateway,
        encryptor: EnvelopeEncryptor,
        consents: ConsentRepository,
        templates: dict[str, Template],
    ) -> None:
        self._projects = projects
        self._documents = documents
        self._texts = texts
        self._storage = storage
        self._encryptor = encryptor
        self._consents = consents
        self._templates = templates

    async def upload(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        type_key: str,
        filename: str,
        content: bytes,
    ) -> DocumentView:
        project = await self._projects.get(project_id, owner)
        template = self._templates[project.template_key]
        doc_type = validate_type_key(type_key, template)

        if len(content) > MAX_DOCUMENT_BYTES:
            raise DocumentValidationError(f"file exceeds {MAX_DOCUMENT_BYTES} bytes")
        sniff_pdf(content)
        text = extract_pdf_text(content)

        if doc_type.model_eligible:
            # Extraction is model preprocessing (ADR 0009 point 2), so the
            # consent gate applies before any text row exists.
            await require_model_consent(
                self._consents, owner, "upload a model-eligible document"
            )

        document_id = uuid.uuid4()
        document = await store_document(
            documents=self._documents,
            texts=self._texts,
            storage=self._storage,
            encryptor=self._encryptor,
            project_id=project_id,
            owner=owner,
            document_id=document_id,
            doc_type=doc_type,
            filename=filename,
            content=content,
            text=text,
        )
        return _view(document)

    async def list(self, project_id: uuid.UUID, owner: uuid.UUID) -> list[DocumentView]:
        await self._projects.get(project_id, owner)
        documents: Sequence[Document] = await self._documents.list_for_project(
            project_id
        )
        return [_view(d) for d in documents]

    async def delete(
        self, project_id: uuid.UUID, owner: uuid.UUID, document_id: uuid.UUID
    ) -> None:
        await self._projects.get(project_id, owner)
        document = await self._documents.get(document_id, project_id)
        # Storage first: a failure leaves an orphan object (harmless), while
        # the other order would leave a row whose download always fails.
        await self._storage.delete(document.storage_key)
        await self._texts.delete_for_document(document_id)
        await self._documents.delete(document_id)

    async def download(
        self, project_id: uuid.UUID, owner: uuid.UUID, document_id: uuid.UUID
    ) -> DownloadedDocument:
        await self._projects.get(project_id, owner)
        document = await self._documents.get(document_id, project_id)

        encrypted = b"".join(
            [chunk async for chunk in self._storage.read(document.storage_key)]
        )
        content = self._encryptor.decrypt(encrypted, document.encrypted_data_key)
        if checksum_sha256(content) != document.checksum_sha256:
            raise ValueError(f"checksum mismatch for document {document_id}")
        return DownloadedDocument(
            original_filename=document.original_filename, content=content
        )
