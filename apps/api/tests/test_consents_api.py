"""Consent API: grant, list, withdraw, re-grant (us-4 item 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.integration


async def test_grant_list_withdraw_lifecycle(client: AsyncTestClient[Any]) -> None:
    empty = await client.get("/api/v1/account/consents")
    assert empty.status_code == 200
    assert empty.json()["data"] == []

    granted = await client.post(
        "/api/v1/account/consents", json={"kind": "model_processing"}
    )
    assert granted.status_code == 201, granted.text
    assert granted.json()["kind"] == "model_processing"
    assert granted.json()["granted_at"] is not None
    assert granted.json()["withdrawn_at"] is None

    listed = await client.get("/api/v1/account/consents")
    assert [c["kind"] for c in listed.json()["data"]] == ["model_processing"]

    withdrawn = await client.delete("/api/v1/account/consents/model_processing")
    assert withdrawn.status_code == 204

    listed_after = await client.get("/api/v1/account/consents")
    consent = listed_after.json()["data"][0]
    assert consent["withdrawn_at"] is not None

    # Withdrawing again fails: there is nothing active to withdraw.
    twice = await client.delete("/api/v1/account/consents/model_processing")
    assert twice.status_code == 404


async def test_regrant_reactivates_the_withdrawn_consent(
    client: AsyncTestClient[Any],
) -> None:
    await client.post("/api/v1/account/consents", json={"kind": "model_processing"})
    await client.delete("/api/v1/account/consents/model_processing")

    regranted = await client.post(
        "/api/v1/account/consents", json={"kind": "model_processing"}
    )
    assert regranted.status_code == 201
    listed = await client.get("/api/v1/account/consents")
    # One row per kind, back to active.
    data = listed.json()["data"]
    assert len(data) == 1
    assert data[0]["withdrawn_at"] is None


async def test_grant_rejects_kind_outside_the_enum(
    client: AsyncTestClient[Any],
) -> None:
    response = await client.post(
        "/api/v1/account/consents", json={"kind": "newsletter"}
    )
    assert response.status_code == 422


async def test_withdraw_rejects_kind_outside_the_enum(
    client: AsyncTestClient[Any],
) -> None:
    response = await client.delete("/api/v1/account/consents/newsletter")
    assert response.status_code == 422


async def test_withdraw_of_unknown_consent_kind_is_not_found(
    client: AsyncTestClient[Any],
) -> None:
    response = await client.delete("/api/v1/account/consents/model_processing")
    assert response.status_code == 404
