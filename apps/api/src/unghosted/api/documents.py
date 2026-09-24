"""Document endpoints: upload, list, delete, streamed download (us-4)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import PurePath
from typing import Annotated

from litestar import Controller, delete, get, post
from litestar.datastructures import UploadFile
from litestar.di import NamedDependency
from litestar.enums import RequestEncodingType
from litestar.exceptions import (
    HTTPException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.params import Body, FromPath
from litestar.response import Stream
from litestar.status_codes import HTTP_204_NO_CONTENT, HTTP_500_INTERNAL_SERVER_ERROR

from unghosted.domain.documents import DocumentValidationError
from unghosted.gateways.storage import StorageError
from unghosted.repositories.documents import DocumentNotFoundError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import DocumentList, DocumentRead, DocumentUploadForm
from unghosted.services.consents import ConsentRequiredError
from unghosted.services.documents import DocumentService


class DocumentController(Controller):
    path = "/projects/{project_id:uuid}/documents"

    @post(status_code=201)
    async def upload_document(
        self,
        project_id: FromPath[uuid.UUID],
        data: Annotated[
            DocumentUploadForm, Body(media_type=RequestEncodingType.MULTI_PART)
        ],
        document_service: NamedDependency[DocumentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DocumentRead:
        upload: UploadFile = data.file
        content = await upload.read()
        # Browsers may send a full local path; storage keys are app-generated
        # and the display name keeps only the basename, quotes stripped.
        filename = (upload.filename or "upload.pdf").replace('"', "")
        original_filename = PurePath(filename).name or "upload.pdf"
        try:
            view = await document_service.upload(
                project_id,
                current_user,
                type_key=data.type_key.strip(),
                filename=original_filename,
                content=content,
            )
        except DocumentValidationError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "validation_failed"}
            ) from exc
        except ConsentRequiredError as exc:
            raise PermissionDeniedException(
                detail=str(exc), extra={"code": "consent_required"}
            ) from exc
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except StorageError as exc:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="document storage failed",
                extra={"code": "storage_error"},
            ) from exc
        return DocumentRead(
            id=view.id,
            type_key=view.type_key,
            model_eligible=view.model_eligible,
            original_filename=view.original_filename,
            size_bytes=view.size_bytes,
            created_at=view.created_at,
        )

    @get()
    async def list_documents(
        self,
        project_id: FromPath[uuid.UUID],
        document_service: NamedDependency[DocumentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DocumentList:
        try:
            views = await document_service.list(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        return DocumentList(
            data=[
                DocumentRead(
                    id=v.id,
                    type_key=v.type_key,
                    model_eligible=v.model_eligible,
                    original_filename=v.original_filename,
                    size_bytes=v.size_bytes,
                    created_at=v.created_at,
                )
                for v in views
            ]
        )

    @delete("/{document_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_document(
        self,
        project_id: FromPath[uuid.UUID],
        document_id: FromPath[uuid.UUID],
        document_service: NamedDependency[DocumentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> None:
        try:
            await document_service.delete(project_id, current_user, document_id)
        except (ProjectNotFoundError, DocumentNotFoundError) as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found"
                if isinstance(exc, ProjectNotFoundError)
                else f"document {document_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except StorageError as exc:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="document storage failed",
                extra={"code": "storage_error"},
            ) from exc

    @get("/{document_id:uuid}/download")
    async def download_document(
        self,
        project_id: FromPath[uuid.UUID],
        document_id: FromPath[uuid.UUID],
        document_service: NamedDependency[DocumentService],
        current_user: NamedDependency[uuid.UUID],
    ) -> Stream:
        """Streamed through the API with the ownership check inside the
        service; never presigned, never inline from the app origin
        (us-4 item 4, ADR 0001)."""
        try:
            downloaded = await document_service.download(
                project_id, current_user, document_id
            )
        except ProjectNotFoundError as exc:
            raise NotFoundException(
                detail=f"project {project_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except DocumentNotFoundError as exc:
            raise NotFoundException(
                detail=f"document {document_id} not found",
                extra={"code": "not_found"},
            ) from exc
        except (StorageError, ValueError) as exc:
            # Checksum mismatch or unreadable object: fail closed rather
            # than serve tampered content (us-4 item 4).
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="document storage failed",
                extra={"code": "storage_error"},
            ) from exc

        async def stream() -> AsyncIterator[bytes]:
            yield downloaded.content

        return Stream(
            stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{downloaded.original_filename}"'
                ),
            },
        )
