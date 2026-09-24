"""Document service: validation, consent gate, write order, download
integrity — all with fakes, no database (us-4 items 1, 2, 4)."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from test_documents import make_pdf
from unghosted.domain.documents import MAX_DOCUMENT_BYTES, DocumentValidationError
from unghosted.gateways.encrypt import EnvelopeEncryptor
from unghosted.services.consents import ConsentRequiredError, require_model_consent
from unghosted.services.documents import DocumentService

OWNER = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
MASTER_KEY = b"0" * 32


@dataclass
class FakeProject:
    id: uuid.UUID
    owner: uuid.UUID
    template_key: str = "apprenticeship-search"


class FakeProjectRepository:
    """Only `get` is used; it enforces ownership like the real one."""

    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, FakeProject] = {}

    async def get(self, project_id: uuid.UUID, owner: uuid.UUID) -> FakeProject:
        from unghosted.repositories.projects import ProjectNotFoundError

        project = self.projects.get(project_id)
        if project is None or project.owner != owner:
            raise ProjectNotFoundError(str(project_id))
        return project


@dataclass
class FakeDocument:
    id: uuid.UUID
    project_id: uuid.UUID
    type_key: str
    model_eligible: bool
    storage_key: str
    original_filename: str
    size_bytes: int
    checksum_sha256: str
    encrypted_data_key: bytes
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, FakeDocument] = {}
        self.calls: list[str] = []

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
    ) -> FakeDocument:
        self.calls.append("documents.create")
        row = FakeDocument(
            id=document_id,
            project_id=project_id,
            type_key=type_key,
            model_eligible=model_eligible,
            storage_key=storage_key,
            original_filename=original_filename,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            encrypted_data_key=encrypted_data_key,
        )
        self.rows[row.id] = row
        return row

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[FakeDocument]:
        return [d for d in self.rows.values() if d.project_id == project_id]

    async def get(self, document_id: uuid.UUID, project_id: uuid.UUID) -> FakeDocument:
        from unghosted.repositories.documents import DocumentNotFoundError

        row = self.rows.get(document_id)
        if row is None or row.project_id != project_id:
            raise DocumentNotFoundError(str(document_id))
        return row

    async def delete(self, document_id: uuid.UUID) -> None:
        self.calls.append("documents.delete")
        self.rows.pop(document_id, None)


class FakeTextRepository:
    def __init__(self) -> None:
        self.texts: dict[uuid.UUID, str] = {}
        self.calls: list[str] = []

    async def create(self, document_id: uuid.UUID, text: str) -> None:
        self.calls.append("texts.create")
        self.texts[document_id] = text

    async def delete_for_document(self, document_id: uuid.UUID) -> None:
        self.calls.append("texts.delete")
        self.texts.pop(document_id, None)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[str] = []

    async def write(self, key: str, data: bytes) -> None:
        self.calls.append("storage.write")
        self.objects[key] = data

    def read(self, key: str) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            self.calls.append("storage.read")
            if key not in self.objects:
                from unghosted.gateways.storage import StorageError

                raise StorageError(f"missing storage key: {key}")
            yield self.objects[key]

        return stream()

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def delete(self, key: str) -> None:
        self.calls.append("storage.delete")
        self.objects.pop(key, None)


class FakeConsentRepository:
    def __init__(self, active: bool) -> None:
        self._active = active

    async def has_active(self, user_id: uuid.UUID, kind: str) -> bool:
        return self._active


def build_service(
    *, consent_active: bool = True
) -> tuple[DocumentService, FakeDocumentRepository, FakeTextRepository, FakeStorage]:
    from unghosted.domain.templates import load_templates

    projects = FakeProjectRepository()
    projects.projects[PROJECT_ID] = FakeProject(PROJECT_ID, OWNER)
    documents = FakeDocumentRepository()
    texts = FakeTextRepository()
    storage = FakeStorage()
    # The fakes mirror the repository method surface the service calls; the
    # real classes are AsyncSession-bound, so the constructor types do not
    # accept them even though every call matches.
    service = DocumentService(
        projects=projects,  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        texts=texts,  # type: ignore[arg-type]
        storage=storage,
        encryptor=EnvelopeEncryptor(MASTER_KEY),
        consents=FakeConsentRepository(consent_active),  # type: ignore[arg-type]
        templates=load_templates(Path(os.environ["UNGHOSTED_SHARED_TEMPLATES_DIR"])),
    )
    return service, documents, texts, storage


async def test_upload_of_eligible_document_writes_row_then_storage_then_text() -> None:
    """ADR 0006 write order: the Postgres row owns identity, the storage
    object follows, the derived text row lands last. The call sequence
    proves the order; the row existing before the object means a storage
    failure rolls back to a consistent state."""
    service, documents, texts, storage = build_service()
    view = await service.upload(
        PROJECT_ID, OWNER, type_key="cv", filename="cv.pdf", content=make_pdf()
    )
    assert view.type_key == "cv"
    assert view.model_eligible is True
    assert view.original_filename == "cv.pdf"
    assert view.size_bytes > 0
    assert documents.calls == ["documents.create"]
    assert storage.calls == ["storage.write"]
    assert texts.calls == ["texts.create"]
    assert list(texts.texts.values()) == [""]


async def test_upload_of_eligible_type_without_consent_is_refused() -> None:
    """No row, no storage object, no extracted text: a refused upload
    leaves no trace behind."""
    service, documents, texts, storage = build_service(consent_active=False)
    with pytest.raises(ConsentRequiredError, match="consent is required"):
        await service.upload(
            PROJECT_ID, OWNER, type_key="cv", filename="cv.pdf", content=make_pdf()
        )
    assert documents.rows == {}
    assert storage.objects == {}
    assert texts.texts == {}


async def test_upload_of_ineligible_type_needs_no_consent() -> None:
    """ADR 0009: ineligible types are stored and listed but never extracted
    or sent to the model, so the consent gate does not apply."""
    service, _, texts, _ = build_service(consent_active=False)
    view = await service.upload(
        PROJECT_ID, OWNER, type_key="id_document", filename="id.pdf", content=make_pdf()
    )
    assert view.model_eligible is False
    assert texts.texts == {}


async def test_upload_rejects_unknown_type() -> None:
    service, *_ = build_service()
    with pytest.raises(DocumentValidationError, match="unknown document type"):
        await service.upload(
            PROJECT_ID, OWNER, type_key="transcript", filename="t.pdf", content=b"%PDF"
        )


async def test_upload_rejects_oversized_file() -> None:
    service, *_ = build_service()
    with pytest.raises(DocumentValidationError, match="exceeds"):
        await service.upload(
            PROJECT_ID,
            OWNER,
            type_key="cv",
            filename="big.pdf",
            content=b"%PDF-" + b"x" * (MAX_DOCUMENT_BYTES + 1),
        )


async def test_upload_rejects_non_pdf_content() -> None:
    service, *_ = build_service()
    with pytest.raises(DocumentValidationError, match="not a PDF"):
        await service.upload(
            PROJECT_ID,
            OWNER,
            type_key="cv",
            filename="cv.pdf",
            content=b"<html>nope</html>",
        )


async def test_download_roundtrips_the_original_bytes() -> None:
    service, *_ = build_service()
    content = make_pdf()
    view = await service.upload(
        PROJECT_ID, OWNER, type_key="cv", filename="cv.pdf", content=content
    )
    downloaded = await service.download(PROJECT_ID, OWNER, uuid.UUID(view.id))
    assert downloaded.content == content
    assert downloaded.original_filename == "cv.pdf"


async def test_download_fails_closed_on_checksum_mismatch() -> None:
    """Tampered storage bytes never reach the client: the checksum is
    verified after decryption (us-4 item 4)."""
    service, documents, _, storage = build_service()
    content = make_pdf()
    view = await service.upload(
        PROJECT_ID, OWNER, type_key="cv", filename="cv.pdf", content=content
    )
    document_id = uuid.UUID(view.id)
    key = documents.rows[document_id].storage_key
    encrypted, wrapped = EnvelopeEncryptor(MASTER_KEY).encrypt(b"tampered bytes")
    storage.objects[key] = encrypted
    documents.rows[document_id].encrypted_data_key = wrapped
    with pytest.raises(ValueError, match="checksum mismatch"):
        await service.download(PROJECT_ID, OWNER, document_id)


async def test_delete_removes_the_storage_object_before_the_rows() -> None:
    """Delete order: storage first — an orphan object is harmless, a row
    whose download always fails is not."""
    service, documents, texts, storage = build_service()
    view = await service.upload(
        PROJECT_ID, OWNER, type_key="cv", filename="cv.pdf", content=make_pdf()
    )
    await service.delete(PROJECT_ID, OWNER, uuid.UUID(view.id))
    assert storage.calls == ["storage.write", "storage.delete"]
    assert documents.calls == ["documents.create", "documents.delete"]
    assert texts.calls == ["texts.create", "texts.delete"]
    assert storage.objects == {}
    assert documents.rows == {}
    assert texts.texts == {}


async def test_upload_for_missing_project_is_not_found() -> None:
    from unghosted.repositories.projects import ProjectNotFoundError

    service, *_ = build_service()
    with pytest.raises(ProjectNotFoundError):
        await service.upload(
            uuid.UUID(int=1), OWNER, type_key="cv", filename="cv.pdf", content=b"%PDF"
        )


async def test_require_model_consent_refusal_names_the_refused_action() -> None:
    """One gate function backs both upload and profile drafting; a consent
    refusal must carry the action that was refused."""
    consents = FakeConsentRepository(False)
    with pytest.raises(ConsentRequiredError, match="draft a profile"):
        await require_model_consent(consents, OWNER, "draft a profile")  # type: ignore[arg-type]
