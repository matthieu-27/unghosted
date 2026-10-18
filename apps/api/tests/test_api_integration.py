"""API integration: projects CRUD + tracker operations against compose DBs."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from conftest import create_project, issue_token

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


async def _insert_row(
    client: AsyncTestClient[Any], project_id: str, revision: int
) -> tuple[str, int]:
    response = await client.patch(
        f"/api/v1/projects/{project_id}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [{"op": "insert_rows", "count": 1}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    tracker = await client.get(f"/api/v1/projects/{project_id}/tracker")
    row_id = str(tracker.json()["rows"][0]["id"])
    return row_id, int(body["revision"])


async def test_project_crud_roundtrip(client: AsyncTestClient[Any]) -> None:
    created = await create_project(
        client, "apprenticeship-search", "Apprenticeship 2027"
    )
    assert created["template_key"] == "apprenticeship-search"
    assert created["archived"] is False
    assert created["document_types"][0] == {
        "key": "cv",
        "label": "CV",
        "model_eligible": True,
    }

    listed = await client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()["data"]] == [created["id"]]

    renamed = await client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Renamed", "archived": True},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"
    assert renamed.json()["archived"] is True

    # Archived projects hide from the default list.
    active = await client.get("/api/v1/projects")
    assert active.json()["data"] == []
    with_archive = await client.get("/api/v1/projects?include_archived=true")
    assert len(with_archive.json()["data"]) == 1

    deleted = await client.delete(f"/api/v1/projects/{created['id']}")
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/projects/{created['id']}")
    assert gone.status_code == 404


async def test_unknown_template_rejected(client: AsyncTestClient[Any]) -> None:
    response = await client.post(
        "/api/v1/projects",
        json={"template_key": "does-not-exist", "name": "X", "settings": {}},
    )
    assert response.status_code == 422


async def test_tracker_fetch_matches_template(client: AsyncTestClient[Any]) -> None:
    created = await create_project(client, "rental-search", "Move to Montreuil")
    tracker = await client.get(f"/api/v1/projects/{created['id']}/tracker")
    assert tracker.status_code == 200
    body = tracker.json()
    assert len(body["definition"]["columns"]) == 14
    assert body["rows"] == []
    assert body["definition"]["revision"] == 0


async def test_operations_set_cell_roundtrip(client: AsyncTestClient[Any]) -> None:
    created = await create_project(client, "apprenticeship-search", "Ops")
    row_id, revision = await _insert_row(client, created["id"], 0)

    response = await client.patch(
        f"/api/v1/projects/{created['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "company",
                    "value": "Acme",
                },
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "status",
                    "value": "sent",
                },
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "date_sent",
                    "value": "2026-09-21",
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    new_revision = response.json()["revision"]

    tracker = await client.get(f"/api/v1/projects/{created['id']}/tracker")
    cells = tracker.json()["rows"][0]["cells"]
    assert cells["company"] == "Acme"
    assert cells["status"] == "sent"
    assert cells["date_sent"] == "2026-09-21"
    assert new_revision == 2


async def test_operations_invalid_value_is_422(client: AsyncTestClient[Any]) -> None:
    created = await create_project(client, "apprenticeship-search", "Invalid")
    row_id, revision = await _insert_row(client, created["id"], 0)
    response = await client.patch(
        f"/api/v1/projects/{created['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "status",
                    "value": "wishful_thinking",
                },
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["extra"]["code"] == "validation_failed"


async def test_operations_system_column_rejected(client: AsyncTestClient[Any]) -> None:
    created = await create_project(client, "apprenticeship-search", "System")
    row_id, revision = await _insert_row(client, created["id"], 0)
    response = await client.patch(
        f"/api/v1/projects/{created['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "response_date",
                    "value": "2026-09-21",
                },
            ],
        },
    )
    assert response.status_code == 422


async def test_stale_revision_conflicts(client: AsyncTestClient[Any]) -> None:
    created = await create_project(client, "apprenticeship-search", "Conflict")
    _row_id, revision = await _insert_row(client, created["id"], 0)

    stale = await client.patch(
        f"/api/v1/projects/{created['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [{"op": "insert_rows", "count": 1}],
        },
    )
    assert stale.status_code == 200

    replay = await client.patch(
        f"/api/v1/projects/{created['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [{"op": "insert_rows", "count": 1}],
        },
    )
    assert replay.status_code == 409
    extra = replay.json()["extra"]
    assert extra["code"] == "stale_revision"
    assert extra["current_revision"] == revision + 1


async def test_other_users_project_is_404(
    client: AsyncTestClient[Any],
    # gitleaks:allow — a pytest fixture parameter, not a credential.
    signing_key: Ed25519PrivateKey,
) -> None:
    created = await create_project(client, "rental-search", "Mine")
    unknown = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert unknown.status_code == 404

    # IDOR: a second signed-in user asking for someone else's project gets
    # 404, not 403 — existence itself stays private (us-6, NFR security).
    stranger_token = issue_token(signing_key, subject=uuid.uuid4())
    stranger = await client.get(
        f"/api/v1/projects/{created['id']}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert stranger.status_code == 404

    listing = await client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {stranger_token}"}
    )
    assert listing.status_code == 200
    assert listing.json()["data"] == []

    mine = await client.get(f"/api/v1/projects/{created['id']}")
    assert mine.status_code == 200


async def test_requests_without_a_token_are_401(client: AsyncTestClient[Any]) -> None:
    response = await client.get("/api/v1/projects", headers={"Authorization": ""})
    assert response.status_code == 401
    assert response.json()["extra"]["code"] == "unauthenticated"


async def test_health_stays_public(client: AsyncTestClient[Any]) -> None:
    response = await client.get("/api/v1/health", headers={"Authorization": ""})
    assert response.status_code == 200


async def test_strict_typing_rejects_coercible_shapes(
    client: AsyncTestClient[Any],
) -> None:
    # base_revision "2" must not silently become the integer 2 (strict wire).
    response = await client.patch(
        "/api/v1/projects/00000000-0000-4000-8000-000000000001/tracker/operations",
        json={"base_revision": "2", "operations": []},
    )
    assert response.status_code == 422
    # project settings: numbers must arrive as JSON numbers, not strings
    response = await client.post(
        "/api/v1/projects",
        json={
            "template_key": "apprenticeship-search",
            "name": "Strict",
            "settings": {"no_response_threshold_days": "21"},
        },
    )
    assert response.status_code == 422
