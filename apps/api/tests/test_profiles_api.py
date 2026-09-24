"""Profile API: draft/edit/approve lifecycle against the compose DBs (us-4
item 3). The model gateway is replaced per test through app state, so the
HTTP path runs without a provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from conftest import create_project
from test_documents import make_pdf
from test_profile_service import RecordingModel

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


async def prepare_project(client: AsyncTestClient[Any]) -> dict[str, Any]:
    """A project with model-processing consent and one eligible document."""
    response = await client.post(
        "/api/v1/account/consents", json={"kind": "model_processing"}
    )
    assert response.status_code == 201, response.text
    project = await create_project(client, "apprenticeship-search", "Search")
    upload = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("cv.pdf", make_pdf(), "application/pdf")},
        data={"type_key": "cv"},
    )
    assert upload.status_code == 201, upload.text
    return project


def install_model(app: Litestar, model: RecordingModel) -> None:
    """provide_profile_service reads state at request time, so a per-test
    gateway lands without rebuilding the app."""
    app.state["model_gateway"] = model


async def test_profile_state_is_empty_before_any_draft(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await client.get(f"/api/v1/projects/{project['id']}/profile")
    assert response.status_code == 200
    assert response.json() == {"approved": None, "draft": None, "versions": []}


async def test_draft_refused_after_consent_withdrawal(
    client: AsyncTestClient[Any],
) -> None:
    """A withdrawn consent gates future drafts: the upload happened while
    consent was active, the draft after withdrawal is refused."""
    project = await prepare_project(client)
    withdrawn = await client.delete("/api/v1/account/consents/model_processing")
    assert withdrawn.status_code == 204
    response = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert response.status_code == 403, response.text
    assert response.json()["extra"]["code"] == "consent_required"


async def test_draft_fails_without_eligible_documents(
    client: AsyncTestClient[Any],
) -> None:
    response = await client.post("/api/v1/account/consents", json={"kind": "x"})
    assert response.status_code == 422  # guard: literal-validated kinds only
    await client.post("/api/v1/account/consents", json={"kind": "model_processing"})
    project = await create_project(client, "apprenticeship-search", "Search")
    draft = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert draft.status_code == 422, draft.text
    assert draft.json()["extra"]["code"] == "no_eligible_documents"


async def test_draft_fails_without_a_configured_model_provider(
    client: AsyncTestClient[Any],
) -> None:
    """No MISTRAL_API_KEY in tests: the endpoint reports 503, not a crash."""
    project = await prepare_project(client)
    response = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert response.status_code == 503, response.text
    assert response.json()["extra"]["code"] == "model_unavailable"


async def test_draft_edit_approve_lifecycle_over_http(
    client: AsyncTestClient[Any],
) -> None:
    model = RecordingModel()
    install_model(client.app, model)
    project = await prepare_project(client)

    drafted = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert drafted.status_code == 200, drafted.text
    version = drafted.json()
    assert version["version"] == 1
    assert version["status"] == "draft"
    assert [h["id"] for h in version["highlights"]] == ["h1", "h2"]
    assert len(model.tasks) == 1

    edited = await client.patch(
        f"/api/v1/projects/{project['id']}/profile/versions/1",
        json={"headline": "Hand-tuned headline"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["headline"] == "Hand-tuned headline"
    # Absent fields keep their drafted values.
    assert edited.json()["seeking"] == "A work-study data role"

    approved = await client.post(
        f"/api/v1/projects/{project['id']}/profile/versions/1/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"] is not None

    # The approved version is immutable over HTTP too.
    conflict = await client.patch(
        f"/api/v1/projects/{project['id']}/profile/versions/1",
        json={"headline": "No longer editable"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["extra"]["code"] == "version_not_editable"

    # Regen drafts a new version; the approved one is untouched.
    regen = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert regen.status_code == 200, regen.text
    assert regen.json()["version"] == 2
    state = await client.get(f"/api/v1/projects/{project['id']}/profile")
    body = state.json()
    assert body["approved"]["version"] == 1
    assert body["approved"]["headline"] == "Hand-tuned headline"
    assert body["draft"]["version"] == 2
    assert [v["version"] for v in body["versions"]] == [1, 2]


async def test_edit_and_approve_of_unknown_version_are_not_found(
    client: AsyncTestClient[Any],
) -> None:
    project = await prepare_project(client)
    edited = await client.patch(
        f"/api/v1/projects/{project['id']}/profile/versions/99",
        json={"headline": "Nope"},
    )
    assert edited.status_code == 404
    approved = await client.post(
        f"/api/v1/projects/{project['id']}/profile/versions/99/approve"
    )
    assert approved.status_code == 404


async def test_profile_endpoints_for_missing_project_are_not_found(
    client: AsyncTestClient[Any],
) -> None:
    missing = "00000000-0000-4000-8000-000000000404"
    state = await client.get(f"/api/v1/projects/{missing}/profile")
    assert state.status_code == 404
    draft = await client.post(f"/api/v1/projects/{missing}/profile/drafts")
    assert draft.status_code == 404
