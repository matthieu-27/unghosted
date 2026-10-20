"""Contact service: CRUD, detail panel, cross-store delete (us-7).

Ownership flows through ProjectRepository.get, like every other project
resource: a contact id from another project is indistinguishable from a
missing one.

The contact↔row relation lives twice on purpose (ADR 0001 data split): the
tracker cell in Mongo is what the user edits, `app.contact_row_links` is the
Postgres index that makes "which rows does this contact serve?" a cheap
query. Deleting a contact therefore needs a compensation step, and anything
the compensation misses is what the reconciliation command reports.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from unghosted.domain.contacts import ContactFields, validate_contact
from unghosted.domain.operations import OperationError
from unghosted.repositories.tracker import TrackerNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from unghosted.db.models import Contact
    from unghosted.repositories.contacts import (
        ContactRepository,
        ContactRowLinkRepository,
    )
    from unghosted.repositories.mail import (
        AuditEventRepository,
        EmailMessageRepository,
        EmailThreadRepository,
    )
    from unghosted.repositories.projects import ProjectRepository
    from unghosted.repositories.tracker import TrackerRepository

CONTACT_LINK_COLUMN_TYPE = "contact-link"
CONTACT_DELETED_EVENT = "contact_deleted"

EDITABLE_FIELDS = (
    "name",
    "role",
    "organization",
    "email",
    "phone",
    "profile_url",
    "notes",
)


@dataclass(frozen=True)
class ContactView:
    id: str
    name: str
    role: str | None
    organization: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    notes: str | None
    linked_row_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ContactThreadView:
    id: str
    recipient: str
    message_count: int
    last_message_at: str | None


@dataclass(frozen=True)
class ContactDetailView:
    contact: ContactView
    linked_row_ids: list[str]
    threads: list[ContactThreadView]


@dataclass(frozen=True)
class ContactDeletionView:
    """What the cross-store delete actually did (us-7 item 3)."""

    links_removed: int
    rows_cleared: int


def _view(contact: Contact, linked_row_count: int) -> ContactView:
    return ContactView(
        id=str(contact.id),
        name=contact.name,
        role=contact.role,
        organization=contact.organization,
        email=contact.email,
        phone=contact.phone,
        profile_url=contact.profile_url,
        notes=contact.notes,
        linked_row_count=linked_row_count,
        created_at=contact.created_at.isoformat(),
        updated_at=contact.updated_at.isoformat(),
    )


def contact_link_column_keys(definition: dict[str, Any]) -> list[str]:
    """Keys of the definition's contact-link columns."""
    columns: list[dict[str, Any]] = definition.get("columns", [])
    return [
        str(column["key"])
        for column in columns
        if column.get("type") == CONTACT_LINK_COLUMN_TYPE
    ]


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _text(value: Any) -> str | None:
    """One wire value as text. HTTP bodies arrive typed by the strict DTO;
    any other caller (CLI, a future import) hands over whatever it has, and
    coercing keeps one validation path for all of them."""
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _clean(fields: dict[str, Any]) -> ContactFields:
    """Validate a full set of contact values, whatever their origin."""
    return validate_contact(
        name=_text(fields.get("name")) or "",
        role=_text(fields.get("role")),
        organization=_text(fields.get("organization")),
        email=_text(fields.get("email")),
        phone=_text(fields.get("phone")),
        profile_url=_text(fields.get("profile_url")),
        notes=_text(fields.get("notes")),
    )


class ContactService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        contacts: ContactRepository,
        links: ContactRowLinkRepository,
        tracker: TrackerRepository,
        threads: EmailThreadRepository,
        messages: EmailMessageRepository,
        audit: AuditEventRepository,
    ) -> None:
        self._projects = projects
        self._contacts = contacts
        self._links = links
        self._tracker = tracker
        self._threads = threads
        self._messages = messages
        self._audit = audit

    async def list(
        self, project_id: uuid.UUID, owner: uuid.UUID, *, query: str | None = None
    ) -> list[ContactView]:
        await self._projects.get(project_id, owner)
        contacts = await self._contacts.list_for_project(project_id, query=query)
        counts = await self._links.count_by_contact(project_id)
        return [_view(contact, counts.get(contact.id, 0)) for contact in contacts]

    async def get(
        self, project_id: uuid.UUID, owner: uuid.UUID, contact_id: uuid.UUID
    ) -> ContactDetailView:
        """The detail panel: the contact, the rows it is linked to, and the
        mail threads addressed to it (us-7 item 1)."""
        await self._projects.get(project_id, owner)
        contact = await self._contacts.get(contact_id, project_id)
        links = await self._links.list_for_contact(contact_id)
        threads = (
            await self._threads.list_for_recipient(project_id, contact.email)
            if contact.email
            else []
        )
        stats = await self._messages.thread_stats([thread.id for thread in threads])
        return ContactDetailView(
            contact=_view(contact, len(links)),
            linked_row_ids=[link.row_id for link in links],
            threads=[
                ContactThreadView(
                    id=str(thread.id),
                    recipient=thread.recipient,
                    message_count=stats.get(thread.id, (0, None))[0],
                    last_message_at=_isoformat(stats.get(thread.id, (0, None))[1]),
                )
                for thread in threads
            ],
        )

    async def create(
        self, project_id: uuid.UUID, owner: uuid.UUID, *, fields: dict[str, Any]
    ) -> ContactView:
        await self._projects.get(project_id, owner)
        contact = await self._contacts.create(project_id, _clean(fields))
        return _view(contact, 0)

    async def update(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        changes: dict[str, Any],
    ) -> ContactView:
        """PATCH semantics: an absent key keeps the stored value, an explicit
        null clears it. The caller passes only the keys the client sent."""
        await self._projects.get(project_id, owner)
        contact = await self._contacts.get(contact_id, project_id)
        merged = {
            key: changes[key] if key in changes else getattr(contact, key)
            for key in EDITABLE_FIELDS
        }
        updated = await self._contacts.update(contact, _clean(merged))
        links = await self._links.list_for_contact(contact_id)
        return _view(updated, len(links))

    async def delete(
        self, project_id: uuid.UUID, owner: uuid.UUID, contact_id: uuid.UUID
    ) -> ContactDeletionView:
        """Delete across both stores (us-7 item 3).

        Postgres first — it owns the contact's identity, and its link rows
        go with it through ON DELETE CASCADE. The Mongo cells are cleaned
        afterwards as a compensation: a failure there leaves ids the
        reconciliation command reports, never a contact that half exists.
        The tracker rows themselves survive: the link is a cell, not the row.
        """
        await self._projects.get(project_id, owner)
        contact = await self._contacts.get(contact_id, project_id)
        links = await self._links.list_for_contact(contact_id)
        await self._contacts.delete(contact_id)
        rows_cleared = await self._clear_contact_cells(project_id, contact_id)
        await self._audit.record(
            user_id=owner,
            project_id=project_id,
            kind=CONTACT_DELETED_EVENT,
            detail={
                "contact_id": str(contact_id),
                "name": contact.name,
                "links_removed": len(links),
                "rows_cleared": rows_cleared,
            },
        )
        return ContactDeletionView(links_removed=len(links), rows_cleared=rows_cleared)

    async def _clear_contact_cells(
        self, project_id: uuid.UUID, contact_id: uuid.UUID
    ) -> int:
        try:
            definition = await self._tracker.get_definition(project_id)
        except TrackerNotFoundError:
            return 0
        return await self._tracker.pull_from_cells(
            project_id, contact_link_column_keys(definition), contact_id
        )


def _cell_contact_ids(rows: Any, column_keys: list[str]) -> list[uuid.UUID]:
    """Every valid contact id the given rows hold in their contact-link
    cells, de-duplicated, order-stable. Invalid entries are skipped: they
    are the reconciler's `unknown` class, not something to index."""
    ids: list[uuid.UUID] = []
    for row in rows:
        cells: dict[str, Any] = row.get("cells", {})
        for key in column_keys:
            for raw in cells.get(key, []) or []:
                contact_id = _as_uuid(raw)
                if contact_id is not None and contact_id not in ids:
                    ids.append(contact_id)
    return ids


class ContactLinkIndexer:
    """Keeps ``app.contact_row_links`` in step with the contact-link cells
    (us-7 item 2). The Mongo cell is what the user edits; the Postgres table
    is its index. One collaborator, so TrackerService needs no contact
    repositories of its own.

    Ordering (the reviewed tradeoff): ids are validated BEFORE the Mongo
    write — an unknown or foreign contact id is a 422 and never reaches a
    cell. The index sync runs AFTER the write and a failure propagates: the
    request fails loudly, Postgres rolls back, and the client retrying the
    idempotent batch heals the gap. Only a process crash between the two
    writes leaves what `contacts-reconcile` reports.
    """

    def __init__(
        self,
        *,
        contacts: ContactRepository,
        links: ContactRowLinkRepository,
    ) -> None:
        self._contacts = contacts
        self._links = links

    async def validate(
        self, project_id: uuid.UUID, *, column_keys: list[str], rows: Any
    ) -> None:
        """Reject ids no contact of this project carries. A contact of
        another project is indistinguishable from a missing one."""
        ids = _cell_contact_ids(rows, column_keys)
        if not ids:
            return
        known = {
            contact.id for contact in await self._contacts.list_by_ids(project_id, ids)
        }
        missing = sorted(
            str(contact_id) for contact_id in ids if contact_id not in known
        )
        if missing:
            raise OperationError(
                f"unknown contact id(s): {', '.join(missing)}",
            )

    async def sync(
        self,
        project_id: uuid.UUID,
        *,
        column_keys: list[str],
        rows: Any,
        deleted_row_ids: list[str],
    ) -> None:
        """Make the link rows match the cells of every touched row, and drop
        the links of rows the batch deleted."""
        for row in rows:
            await self._links.replace_for_row(
                project_id,
                str(row["_id"]),
                _cell_contact_ids([row], column_keys),
            )
        await self._links.delete_for_rows(project_id, deleted_row_ids)


@dataclass(frozen=True)
class OrphanReport:
    """One project's cross-store inconsistencies (us-7 item 3)."""

    project_id: str
    project_name: str
    unknown_contact_ids: list[str]
    """Contact ids still sitting in tracker cells with no contacts row."""
    links_without_row: list[str]
    """Link rows whose tracker row no longer exists in Mongo."""
    links_without_cell: list[str]
    """Link rows the matching tracker cell does not list."""
    cells_without_link: list[str]
    """Cell entries with no link row — the index missed a write."""
    repaired: RepairCounts | None = None
    """What a --repair pass changed; None on a report-only run."""

    @property
    def clean(self) -> bool:
        return not (
            self.unknown_contact_ids
            or self.links_without_row
            or self.links_without_cell
            or self.cells_without_link
        )


@dataclass(frozen=True)
class RepairCounts:
    """What one --repair pass changed, per orphan class. The rules are
    deterministic and cell-first: where the row still exists the Mongo cell
    is the truth and the Postgres index is rebuilt from it; where it does
    not, the link goes; an id no contact answers to leaves the cells."""

    links_reindexed: int
    """Link rows added or removed to match the cells of surviving rows."""
    links_dropped: int
    """Link rows removed because their tracker row is gone."""
    unknown_ids_cleared: int
    """Ids pulled out of cells because no contact carries them."""


def _pair(row_id: str, contact_id: str) -> str:
    return f"{row_id}:{contact_id}"


class ContactReconciler:
    """Cross-store check behind the `contacts-reconcile` command.

    It reports by default: a maintenance command silently rewriting user
    data is the wrong default. `--repair` opts into the deterministic,
    cell-first rules in RepairCounts — the same report, plus the fixes.
    """

    def __init__(
        self,
        *,
        projects: ProjectRepository,
        contacts: ContactRepository,
        links: ContactRowLinkRepository,
        tracker: TrackerRepository,
    ) -> None:
        self._projects = projects
        self._contacts = contacts
        self._links = links
        self._tracker = tracker

    async def run(self, *, repair: bool = False) -> list[OrphanReport]:
        reports: list[OrphanReport] = []
        for project in await self._projects.list_all_live():
            reports.append(
                await self.check_project(project.id, project.name, repair=repair)
            )
        return reports

    async def check_project(
        self, project_id: uuid.UUID, project_name: str, *, repair: bool = False
    ) -> OrphanReport:
        try:
            definition = await self._tracker.get_definition(project_id)
        except TrackerNotFoundError:
            definition = {"columns": []}
        column_keys = contact_link_column_keys(definition)
        rows = await self._tracker.list_rows(project_id)
        known_ids = {
            contact.id for contact in await self._contacts.list_for_project(project_id)
        }
        row_ids = {str(row["_id"]) for row in rows}

        cell_pairs: set[str] = set()
        unknown: set[str] = set()
        for row in rows:
            cells: dict[str, Any] = row.get("cells", {})
            for key in column_keys:
                for raw in cells.get(key, []) or []:
                    contact_id = _as_uuid(raw)
                    if contact_id is None:
                        unknown.add(str(raw))
                        continue
                    cell_pairs.add(_pair(str(row["_id"]), str(contact_id)))
                    if contact_id not in known_ids:
                        unknown.add(str(contact_id))

        link_pairs: set[str] = set()
        links_without_row: list[str] = []
        for link in await self._links.list_for_project(project_id):
            link_pairs.add(_pair(link.row_id, str(link.contact_id)))
            if link.row_id not in row_ids:
                links_without_row.append(_pair(link.row_id, str(link.contact_id)))

        report = OrphanReport(
            project_id=str(project_id),
            project_name=project_name,
            unknown_contact_ids=sorted(unknown),
            links_without_row=sorted(links_without_row),
            links_without_cell=sorted(
                pair
                for pair in link_pairs - cell_pairs
                if pair.split(":", 1)[0] in row_ids
            ),
            cells_without_link=sorted(cell_pairs - link_pairs),
        )
        if repair and not report.clean:
            counts = await self._repair(
                project_id, report, rows=rows, column_keys=column_keys
            )
            report = replace(report, repaired=counts)
        return report

    async def _repair(
        self,
        project_id: uuid.UUID,
        report: OrphanReport,
        *,
        rows: list[dict[str, Any]],
        column_keys: list[str],
    ) -> RepairCounts:
        rows_by_id = {str(row["_id"]): row for row in rows}

        # Surviving rows: the cell is the truth, the index is rebuilt. An
        # id no contact answers to is pulled below — re-indexing it would
        # violate the contact foreign key.
        gone = set(report.unknown_contact_ids)
        reindexed = 0
        for row_id in sorted(
            {
                pair.split(":", 1)[0]
                for pair in [*report.links_without_cell, *report.cells_without_link]
            }
        ):
            row = rows_by_id.get(row_id)
            if row is not None:
                reindexed += await self._links.replace_for_row(
                    project_id,
                    row_id,
                    [
                        contact_id
                        for contact_id in _cell_contact_ids([row], column_keys)
                        if str(contact_id) not in gone
                    ],
                )

        # Dead rows: nothing to rebuild from, the link goes.
        dropped = await self._links.delete_pairs(
            project_id,
            [
                (row_id, uuid.UUID(contact_id))
                for row_id, contact_id in (
                    pair.split(":", 1) for pair in report.links_without_row
                )
            ],
        )

        # Ids no contact answers to: pulled out of the cells, both forms.
        values: list[object] = []
        for entry in report.unknown_contact_ids:
            values.append(entry)
            try:
                values.append(uuid.UUID(entry))
            except ValueError:
                pass
        cleared = await self._tracker.pull_from_cells(project_id, column_keys, *values)

        return RepairCounts(
            links_reindexed=reindexed,
            links_dropped=dropped,
            unknown_ids_cleared=cleared,
        )


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def format_reports(reports: Sequence[OrphanReport]) -> str:
    """Plain-text report for the command's stdout."""
    lines: list[str] = []
    for report in reports:
        if report.clean and report.repaired is None:
            continue
        lines.append(f"project {report.project_name} ({report.project_id})")
        for label, entries in (
            ("contact ids in cells with no contact row", report.unknown_contact_ids),
            ("links pointing at a missing tracker row", report.links_without_row),
            ("links the tracker cell does not list", report.links_without_cell),
            ("cell entries with no link row", report.cells_without_link),
        ):
            for entry in entries:
                lines.append(f"  {label}: {entry}")
        if report.repaired is not None:
            counts = report.repaired
            lines.append(
                f"  repaired: {counts.links_reindexed} links re-indexed, "
                f"{counts.links_dropped} links dropped, "
                f"{counts.unknown_ids_cleared} unknown ids cleared"
            )
    if not lines:
        return f"contacts-reconcile: {len(reports)} projects checked, no orphans"
    if any(report.repaired is not None for report in reports):
        lines.append(
            f"contacts-reconcile: {len(reports)} projects checked, "
            "orphans above repaired this run"
        )
    else:
        lines.append(
            f"contacts-reconcile: {len(reports)} projects checked, orphans above"
        )
    return "\n".join(lines)
