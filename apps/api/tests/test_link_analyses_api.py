"""Link-analysis endpoint integration: text path, policy errors, rate limit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from conftest import create_project

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


async def test_text_analysis_returns_manual_fields(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Paste")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/link-analyses",
        json={"input": "Data Engineer chez Acme, Nantes, 45k, CDI"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cached"] is False
    assert body["fields"] == []  # no model configured in tests: manual
    assert body["warnings"] == []


async def test_url_analysis_blocked_for_loopback(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "SSRF")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/link-analyses",
        json={"input": "http://127.0.0.1/admin"},
    )
    assert response.status_code == 422
    assert response.json()["extra"]["code"] == "fetch_blocked"


async def test_url_analysis_blocked_for_metadata_ip(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "rental-search", "Meta")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/link-analyses",
        json={"input": "http://169.254.169.254/latest/meta-data"},
    )
    assert response.status_code == 422
    assert response.json()["extra"]["code"] == "fetch_blocked"


async def test_analysis_records_row_even_when_kind_unknown(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "rental-search", "Plain text")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/link-analyses",
        json={"input": "Bonjour, je cherche un appartement a Montreuil."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page_kind"] is None  # deterministic rules found nothing, no model


async def test_unknown_project_is_404(client: AsyncTestClient[Any]) -> None:
    import uuid

    response = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/link-analyses",
        json={"input": "whatever"},
    )
    assert response.status_code == 404


async def test_rate_limit_kicks_in(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Rate")
    statuses = []
    for i in range(11):
        response = await client.post(
            f"/api/v1/projects/{project['id']}/link-analyses",
            json={"input": f"paste number {i}"},
        )
        statuses.append(response.status_code)
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
    body_429 = response.json()
    assert body_429["extra"]["code"] == "rate_limited"
