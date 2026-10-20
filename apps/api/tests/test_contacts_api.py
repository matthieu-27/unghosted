"""Contacts API against the compose databases (us-7).

Covers the CRUD surface, the contact-link column, and the cross-store
delete: the parts where Postgres and Mongo have to agree.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from conftest import OWNER_USER, create_project, issue_token

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from litestar.testing import AsyncTestClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CONTACT_COLUMN = "contact"


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    """Direct database access for the state no endpoint can create yet
    (mail threads) or should create (deliberately broken link rows)."""
    from unghosted.config import load_settings
    from unghosted.db.sql import create_engine

    engine = create_engine(load_settings())
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            yield session
            await session.commit()
    finally:
        await engine.dispose()


async def create_contact(
    client: AsyncTestClient[Any], project_id: str, **fields: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Martin Dupont"}
    body.update(fields)
    response = await client.post(f"/api/v1/projects/{project_id}/contacts", json=body)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def add_row(client: AsyncTestClient[Any], project_id: str) -> tuple[str, int]:
    """One empty tracker row. Returns its id and the current revision."""
    response = await client.patch(
        f"/api/v1/projects/{project_id}/tracker/operations",
        json={"base_revision": 0, "operations": [{"op": "insert_rows", "count": 1}]},
    )
    assert response.status_code == 200, response.text
    revision = int(response.json()["revision"])
    tracker = await client.get(f"/api/v1/projects/{project_id}/tracker")
    return str(tracker.json()["rows"][0]["id"]), revision


async def link_contacts(
    client: AsyncTestClient[Any],
    project_id: str,
    row_id: str,
    revision: int,
    contact_ids: list[str],
) -> Any:
    return await client.patch(
        f"/api/v1/projects/{project_id}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": CONTACT_COLUMN,
                    "value": contact_ids,
                }
            ],
        },
    )


async def link_row_ids(project_id: str) -> list[tuple[str, str]]:
    from unghosted.db.models import ContactRowLink

    async with db_session() as session:
        stmt = select(ContactRowLink).where(
            ContactRowLink.project_id == uuid.UUID(project_id)
        )
        links = (await session.scalars(stmt)).all()
        return [(link.row_id, str(link.contact_id)) for link in links]


async def row_cells(client: AsyncTestClient[Any], project_id: str) -> list[Any]:
    tracker = await client.get(f"/api/v1/projects/{project_id}/tracker")
    return [row["cells"] for row in tracker.json()["rows"]]


# --- CRUD (us-7 item 1) ----------------------------------------------------


async def test_owner_creates_and_lists_a_contact(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    created = await create_contact(
        client,
        project["id"],
        role="Head of data",
        organization="Le Dojo Club",
        email="martin@dojoclub.example",
        phone="+33 6 01 02 03 04",
        profile_url="https://example.com/in/martin",
        notes="Met at a meetup",
    )
    assert created["name"] == "Martin Dupont"
    assert created["email"] == "martin@dojoclub.example"
    assert created["linked_row_count"] == 0

    listed = await client.get(f"/api/v1/projects/{project['id']}/contacts")
    assert listed.status_code == 200, listed.text
    assert [c["id"] for c in listed.json()["data"]] == [created["id"]]


async def test_contact_list_search_matches_organization_and_email(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    await create_contact(
        client, project["id"], name="Martin Dupont", organization="Le Dojo Club"
    )
    await create_contact(
        client, project["id"], name="Alice Martin", email="alice@other.example"
    )

    by_organization = await client.get(
        f"/api/v1/projects/{project['id']}/contacts", params={"search": "dojo"}
    )
    assert [c["name"] for c in by_organization.json()["data"]] == ["Martin Dupont"]

    by_email = await client.get(
        f"/api/v1/projects/{project['id']}/contacts", params={"search": "other.example"}
    )
    assert [c["name"] for c in by_email.json()["data"]] == ["Alice Martin"]

    # Both names contain "martin": search is one filter, not an exact match.
    by_name = await client.get(
        f"/api/v1/projects/{project['id']}/contacts", params={"search": "martin"}
    )
    assert len(by_name.json()["data"]) == 2


async def test_contact_search_treats_wildcards_literally(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    await create_contact(client, project["id"], name="Martin Dupont")

    response = await client.get(
        f"/api/v1/projects/{project['id']}/contacts", params={"search": "%"}
    )
    assert response.json()["data"] == []


async def test_contact_patch_keeps_absent_fields_and_clears_explicit_nulls(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(
        client,
        project["id"],
        email="martin@dojoclub.example",
        organization="Le Dojo Club",
    )

    patched = await client.patch(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}",
        json={"role": "Data lead", "organization": None},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["role"] == "Data lead"
    assert body["organization"] is None
    assert body["email"] == "martin@dojoclub.example"


async def test_contact_creation_rejects_a_malformed_email(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/contacts",
        json={"name": "Martin", "email": "martin(at)dojoclub"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["extra"]["code"] == "validation_failed"


async def test_contact_creation_rejects_a_blank_name(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/contacts", json={"name": "   "}
    )
    assert response.status_code == 422, response.text


async def test_another_user_cannot_read_a_contact(
    client: AsyncTestClient[Any], signing_key: Ed25519PrivateKey
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])

    intruder = issue_token(signing_key, subject=uuid.uuid4())
    response = await client.get(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}",
        headers={"Authorization": f"Bearer {intruder}"},
    )
    assert response.status_code == 404, response.text


async def test_contact_detail_lists_linked_rows_and_threads(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import EmailMessage, EmailThread

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(
        client, project["id"], email="martin@dojoclub.example"
    )
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    assert linked.status_code == 200, linked.text

    async with db_session() as session:
        thread = EmailThread(
            project_id=uuid.UUID(project["id"]), recipient="martin@dojoclub.example"
        )
        session.add(thread)
        await session.flush()
        session.add(
            EmailMessage(
                project_id=uuid.UUID(project["id"]),
                thread_id=thread.id,
                draft_id=None,
                row_id=row_id,
                sender="me@example.com",
                recipient="martin@dojoclub.example",
                subject="Candidature",
                provider="fake",
                provider_message_id="m-1",
                provider_thread_id=None,
                attachment_document_ids=[],
            )
        )

    detail = await client.get(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}"
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["linked_row_ids"] == [row_id]
    assert body["contact"]["linked_row_count"] == 1
    assert len(body["threads"]) == 1
    assert body["threads"][0]["message_count"] == 1
    assert body["threads"][0]["last_message_at"] is not None


# --- contact-link column (us-7 item 2) -------------------------------------


async def test_linking_a_contact_to_a_row_creates_a_link_row(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])

    response = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    assert response.status_code == 200, response.text
    assert await link_row_ids(project["id"]) == [(row_id, contact["id"])]

    listed = await client.get(f"/api/v1/projects/{project['id']}/contacts")
    assert listed.json()["data"][0]["linked_row_count"] == 1


async def test_unlinking_a_contact_keeps_the_contact(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    revision = int(linked.json()["revision"])

    unlinked = await link_contacts(client, project["id"], row_id, revision, [])
    assert unlinked.status_code == 200, unlinked.text
    assert await link_row_ids(project["id"]) == []

    still_there = await client.get(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}"
    )
    assert still_there.status_code == 200


async def test_linking_an_unknown_contact_is_rejected(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    row_id, revision = await add_row(client, project["id"])

    response = await link_contacts(
        client, project["id"], row_id, revision, [str(uuid.uuid4())]
    )
    assert response.status_code == 422, response.text
    assert await link_row_ids(project["id"]) == []


async def test_linking_a_contact_of_another_project_is_rejected(
    client: AsyncTestClient[Any],
) -> None:
    other = await create_project(client, "apprenticeship-search", "Other search")
    foreign = await create_contact(client, other["id"])
    project = await create_project(client, "apprenticeship-search", "Search")
    row_id, revision = await add_row(client, project["id"])

    response = await link_contacts(
        client, project["id"], row_id, revision, [foreign["id"]]
    )
    assert response.status_code == 422, response.text


async def test_deleting_a_row_removes_its_links(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    revision = int(linked.json()["revision"])

    response = await client.patch(
        f"/api/v1/projects/{project['id']}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [{"op": "delete_rows", "row_ids": [row_id]}],
        },
    )
    assert response.status_code == 200, response.text
    assert await link_row_ids(project["id"]) == []


# --- cross-store delete (us-7 item 3) --------------------------------------


async def test_deleting_a_contact_clears_the_cell_and_keeps_the_row(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import AuditEvent

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    assert linked.status_code == 200, linked.text

    deleted = await client.delete(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}"
    )
    assert deleted.status_code == 204, deleted.text

    gone = await client.get(
        f"/api/v1/projects/{project['id']}/contacts/{contact['id']}"
    )
    assert gone.status_code == 404

    tracker = await client.get(f"/api/v1/projects/{project['id']}/tracker")
    rows = tracker.json()["rows"]
    assert [row["id"] for row in rows] == [row_id]
    assert rows[0]["cells"].get(CONTACT_COLUMN, []) == []
    assert await link_row_ids(project["id"]) == []

    async with db_session() as session:
        stmt = select(AuditEvent).where(
            AuditEvent.project_id == uuid.UUID(project["id"])
        )
        events = [
            (event.kind, dict(event.detail))
            for event in (await session.scalars(stmt)).all()
        ]
    assert [kind for kind, _ in events] == ["contact_deleted"]
    assert events[0][1]["contact_id"] == contact["id"]
    assert events[0][1]["links_removed"] == 1


async def test_deleting_one_contact_leaves_the_other_link_in_the_cell(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    kept = await create_contact(client, project["id"], name="Alice Martin")
    removed = await create_contact(client, project["id"], name="Martin Dupont")
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [kept["id"], removed["id"]]
    )
    assert linked.status_code == 200, linked.text

    deleted = await client.delete(
        f"/api/v1/projects/{project['id']}/contacts/{removed['id']}"
    )
    assert deleted.status_code == 204

    cells = await row_cells(client, project["id"])
    assert cells[0][CONTACT_COLUMN] == [kept["id"]]
    assert await link_row_ids(project["id"]) == [(row_id, kept["id"])]


async def test_deleting_an_unknown_contact_is_not_found(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    response = await client.delete(
        f"/api/v1/projects/{project['id']}/contacts/{uuid.uuid4()}"
    )
    assert response.status_code == 404, response.text


# --- reconciliation command (us-7 item 3) ----------------------------------


async def reconcile_reports(*, repair: bool = False) -> list[Any]:
    from unghosted.config import load_settings
    from unghosted.db.mongo import create_mongo_client, get_tracker_db
    from unghosted.repositories.contacts import (
        ContactRepository,
        ContactRowLinkRepository,
    )
    from unghosted.repositories.projects import ProjectRepository
    from unghosted.repositories.tracker import TrackerRepository
    from unghosted.services.contacts import ContactReconciler

    settings = load_settings()
    mongo = create_mongo_client(settings)
    try:
        async with db_session() as session:
            reconciler = ContactReconciler(
                projects=ProjectRepository(session),
                contacts=ContactRepository(session),
                links=ContactRowLinkRepository(session),
                tracker=TrackerRepository(
                    get_tracker_db(mongo, settings.mongo_database)
                ),
            )
            return await reconciler.run(repair=repair)
    finally:
        await mongo.close()


async def test_reconcile_reports_nothing_on_a_consistent_project(
    client: AsyncTestClient[Any],
) -> None:
    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    await link_contacts(client, project["id"], row_id, revision, [contact["id"]])

    reports = await reconcile_reports()
    assert [report.project_id for report in reports] == [project["id"]]
    assert reports[0].clean


async def test_reconcile_reports_a_cell_whose_link_row_vanished(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import ContactRowLink

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    await link_contacts(client, project["id"], row_id, revision, [contact["id"]])

    # A lost index write is exactly what the command exists to surface.
    async with db_session() as session:
        await session.execute(
            delete(ContactRowLink).where(
                ContactRowLink.project_id == uuid.UUID(project["id"])
            )
        )

    reports = await reconcile_reports()
    assert reports[0].cells_without_link == [f"{row_id}:{contact['id']}"]
    assert not reports[0].clean


async def test_reconcile_reports_a_link_row_pointing_at_a_missing_row(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import ContactRowLink

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])

    async with db_session() as session:
        session.add(
            ContactRowLink(
                project_id=uuid.UUID(project["id"]),
                contact_id=uuid.UUID(contact["id"]),
                row_id="row-that-never-existed",
            )
        )

    reports = await reconcile_reports()
    assert reports[0].links_without_row == [f"row-that-never-existed:{contact['id']}"]


# --- repair (us-7 item 3, the --repair pass) --------------------------------


async def test_repair_reindexes_links_the_index_write_lost(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import ContactRowLink

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    await link_contacts(client, project["id"], row_id, revision, [contact["id"]])

    async with db_session() as session:
        await session.execute(
            delete(ContactRowLink).where(
                ContactRowLink.project_id == uuid.UUID(project["id"])
            )
        )

    reports = await reconcile_reports(repair=True)

    # The cell is the source of truth: the link rows come back from it.
    assert await link_row_ids(project["id"]) == [(row_id, contact["id"])]
    assert reports[0].repaired is not None
    assert reports[0].repaired.links_reindexed == 1

    assert [report.project_id for report in await reconcile_reports()] == [
        project["id"]
    ]
    assert (await reconcile_reports())[0].clean


async def test_repair_drops_links_pointing_at_missing_rows(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import ContactRowLink

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])

    async with db_session() as session:
        session.add(
            ContactRowLink(
                project_id=uuid.UUID(project["id"]),
                contact_id=uuid.UUID(contact["id"]),
                row_id="row-that-never-existed",
            )
        )

    reports = await reconcile_reports(repair=True)

    assert await link_row_ids(project["id"]) == []
    assert reports[0].repaired is not None
    assert reports[0].repaired.links_dropped == 1
    assert (await reconcile_reports())[0].clean


async def test_repair_clears_unknown_ids_out_of_cells(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.db.models import Contact

    project = await create_project(client, "apprenticeship-search", "Search")
    contact = await create_contact(client, project["id"])
    row_id, revision = await add_row(client, project["id"])
    linked = await link_contacts(
        client, project["id"], row_id, revision, [contact["id"]]
    )
    assert linked.status_code == 200, linked.text

    # Delete the contact row directly: the links cascade away, but the cell
    # keeps an id no contact answers to — the crash-window state.
    async with db_session() as session:
        await session.execute(
            delete(Contact).where(Contact.id == uuid.UUID(contact["id"]))
        )

    reports = await reconcile_reports()
    assert reports[0].unknown_contact_ids == [contact["id"]]

    repaired = await reconcile_reports(repair=True)
    assert repaired[0].repaired is not None
    assert repaired[0].repaired.unknown_ids_cleared == 1

    cells = await row_cells(client, project["id"])
    assert cells[0][CONTACT_COLUMN] == []
    assert (await reconcile_reports())[0].clean


async def test_reconcile_report_text_names_the_project(
    client: AsyncTestClient[Any],
) -> None:
    from unghosted.services.contacts import format_reports

    project = await create_project(client, "apprenticeship-search", "Search")
    assert OWNER_USER  # the fixtures run as the seeded owner
    reports = await reconcile_reports()
    text = format_reports(reports)
    assert "no orphans" in text
    assert project["id"] not in text
