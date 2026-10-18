"""Documents API: upload, list, download, delete against the compose DBs
(us-4 items 1, 2, 4)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from conftest import create_project
from test_documents import make_pdf

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


async def grant_model_consent(client: AsyncTestClient[Any]) -> None:
    response = await client.post(
        "/api/v1/account/consents", json={"kind": "model_processing"}
    )
    assert response.status_code == 201, response.text


async def upload_document(
    client: AsyncTestClient[Any],
    project_id: str,
    *,
    type_key: str = "cv",
    filename: str = "cv.pdf",
    content: bytes | None = None,
) -> Any:
    return await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": (filename, content or make_pdf(), "application/pdf")},
        data={"type_key": type_key},
    )


async def test_upload_of_eligible_type_requires_consent(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await upload_document(client, project["id"])
    assert response.status_code == 403, response.text
    assert response.json()["extra"]["code"] == "consent_required"


async def test_upload_list_download_delete_roundtrip(
    client: AsyncTestClient[Any],
) -> None:
    await grant_model_consent(client)
    project = await create_project(client, "apprenticeship-search", "Search")
    content = make_pdf()

    uploaded = await upload_document(
        client, project["id"], content=content, filename="cv.pdf"
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["type_key"] == "cv"
    assert body["model_eligible"] is True
    assert body["original_filename"] == "cv.pdf"
    assert body["size_bytes"] == len(content)

    listed = await client.get(f"/api/v1/projects/{project['id']}/documents")
    assert listed.status_code == 200
    assert [d["id"] for d in listed.json()["data"]] == [body["id"]]

    downloaded = await client.get(
        f"/api/v1/projects/{project['id']}/documents/{body['id']}/download"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.headers["content-disposition"] == 'attachment; filename="cv.pdf"'

    deleted = await client.delete(
        f"/api/v1/projects/{project['id']}/documents/{body['id']}"
    )
    assert deleted.status_code == 204
    listed_again = await client.get(f"/api/v1/projects/{project['id']}/documents")
    assert listed_again.json()["data"] == []
    missing = await client.get(
        f"/api/v1/projects/{project['id']}/documents/{body['id']}/download"
    )
    assert missing.status_code == 404


async def test_ineligible_type_uploads_without_consent(
    client: AsyncTestClient[Any],
) -> None:
    """id_document is stored and listed but never sent to the model (ADR
    0009), so no consent is needed to keep it."""
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await upload_document(client, project["id"], type_key="id_document")
    assert response.status_code == 201, response.text
    assert response.json()["model_eligible"] is False


async def test_upload_rejects_non_pdf_payload(
    client: AsyncTestClient[Any],
) -> None:
    await grant_model_consent(client)
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await upload_document(
        client, project["id"], content=b"<html>not a pdf</html>"
    )
    assert response.status_code == 422
    assert response.json()["extra"]["code"] == "validation_failed"


async def test_upload_rejects_oversized_payload(
    client: AsyncTestClient[Any],
) -> None:
    await grant_model_consent(client)
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await upload_document(
        client,
        project["id"],
        content=b"%PDF-" + b"x" * (3 * 1024 * 1024 + 1),
    )
    assert response.status_code == 422


async def test_upload_rejects_type_outside_the_template(
    client: AsyncTestClient[Any],
) -> None:
    await grant_model_consent(client)
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await upload_document(client, project["id"], type_key="transcript")
    assert response.status_code == 422


async def test_document_endpoints_for_missing_project_are_not_found(
    client: AsyncTestClient[Any],
) -> None:
    missing = uuid.UUID(int=404)
    listed = await client.get(f"/api/v1/projects/{missing}/documents")
    assert listed.status_code == 404
    upload = await upload_document(client, str(missing))
    assert upload.status_code == 404
    download = await client.get(
        f"/api/v1/projects/{missing}/documents/{uuid.UUID(int=1)}/download"
    )
    assert download.status_code == 404
    deleted = await client.delete(
        f"/api/v1/projects/{missing}/documents/{uuid.UUID(int=1)}"
    )
    assert deleted.status_code == 404
