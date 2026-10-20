"""Contact and contact↔row link persistence (PostgreSQL)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import CursorResult, delete, func, or_, select

from unghosted.db.models import Contact, ContactRowLink
from unghosted.domain.contacts import search_pattern

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from unghosted.domain.contacts import ContactFields


class ContactNotFoundError(LookupError):
    """No contact with this id in this project."""


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_project(
        self, project_id: uuid.UUID, *, query: str | None = None
    ) -> Sequence[Contact]:
        stmt = select(Contact).where(Contact.project_id == project_id)
        if query:
            pattern = search_pattern(query)
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(pattern, escape="\\"),
                    Contact.organization.ilike(pattern, escape="\\"),
                    Contact.role.ilike(pattern, escape="\\"),
                    Contact.email.ilike(pattern, escape="\\"),
                )
            )
        stmt = stmt.order_by(func.lower(Contact.name))
        return (await self._session.scalars(stmt)).all()

    async def get(self, contact_id: uuid.UUID, project_id: uuid.UUID) -> Contact:
        contact = await self._session.get(Contact, contact_id)
        if contact is None or contact.project_id != project_id:
            raise ContactNotFoundError(str(contact_id))
        return contact

    async def list_by_ids(
        self, project_id: uuid.UUID, contact_ids: Iterable[uuid.UUID]
    ) -> Sequence[Contact]:
        ids = list(contact_ids)
        if not ids:
            return []
        stmt = select(Contact).where(
            Contact.project_id == project_id, Contact.id.in_(ids)
        )
        return (await self._session.scalars(stmt)).all()

    async def create(self, project_id: uuid.UUID, fields: ContactFields) -> Contact:
        contact = Contact(
            project_id=project_id,
            name=fields.name,
            role=fields.role,
            organization=fields.organization,
            email=fields.email,
            phone=fields.phone,
            profile_url=fields.profile_url,
            notes=fields.notes,
        )
        self._session.add(contact)
        await self._session.flush()
        await self._session.refresh(contact)
        return contact

    async def update(self, contact: Contact, fields: ContactFields) -> Contact:
        """Full replacement of the editable fields: PATCH semantics are
        resolved one layer up, where "absent" and "cleared" are still
        distinguishable."""
        contact.name = fields.name
        contact.role = fields.role
        contact.organization = fields.organization
        contact.email = fields.email
        contact.phone = fields.phone
        contact.profile_url = fields.profile_url
        contact.notes = fields.notes
        await self._session.flush()
        await self._session.refresh(contact)
        return contact

    async def delete(self, contact_id: uuid.UUID) -> None:
        """The contact row only — its links follow through ON DELETE CASCADE."""
        await self._session.execute(delete(Contact).where(Contact.id == contact_id))


class ContactRowLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_contact(self, contact_id: uuid.UUID) -> Sequence[ContactRowLink]:
        stmt = (
            select(ContactRowLink)
            .where(ContactRowLink.contact_id == contact_id)
            .order_by(ContactRowLink.created_at)
        )
        return (await self._session.scalars(stmt)).all()

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[ContactRowLink]:
        stmt = (
            select(ContactRowLink)
            .where(ContactRowLink.project_id == project_id)
            .order_by(ContactRowLink.created_at)
        )
        return (await self._session.scalars(stmt)).all()

    async def count_by_contact(self, project_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Linked-row count per contact, in one grouped query."""
        stmt = (
            select(ContactRowLink.contact_id, func.count())
            .where(ContactRowLink.project_id == project_id)
            .group_by(ContactRowLink.contact_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}

    async def list_for_row(
        self, project_id: uuid.UUID, row_id: str
    ) -> Sequence[ContactRowLink]:
        stmt = (
            select(ContactRowLink)
            .where(
                ContactRowLink.project_id == project_id,
                ContactRowLink.row_id == row_id,
            )
            .order_by(ContactRowLink.created_at)
        )
        return (await self._session.scalars(stmt)).all()

    async def replace_for_row(
        self, project_id: uuid.UUID, row_id: str, contact_ids: Iterable[uuid.UUID]
    ) -> int:
        """Make the link rows match the cell exactly (us-7 item 2): the cell
        in Mongo is what the user edits, the links are its Postgres index.
        Returns how many link rows were added or removed."""
        wanted = list(dict.fromkeys(contact_ids))
        existing = {
            link.contact_id: link
            for link in await self.list_for_row(project_id, row_id)
        }
        changed = 0
        for contact_id, link in existing.items():
            if contact_id not in wanted:
                await self._session.delete(link)
                changed += 1
        for contact_id in wanted:
            if contact_id not in existing:
                self._session.add(
                    ContactRowLink(
                        project_id=project_id, contact_id=contact_id, row_id=row_id
                    )
                )
                changed += 1
        await self._session.flush()
        return changed

    async def delete_for_rows(
        self, project_id: uuid.UUID, row_ids: Iterable[str]
    ) -> None:
        ids = list(row_ids)
        if not ids:
            return
        await self._session.execute(
            delete(ContactRowLink).where(
                ContactRowLink.project_id == project_id,
                ContactRowLink.row_id.in_(ids),
            )
        )

    async def delete_pairs(
        self, project_id: uuid.UUID, pairs: Iterable[tuple[str, uuid.UUID]]
    ) -> int:
        """Remove specific link rows — the repair pass for links pointing at
        rows Mongo no longer has. Returns how many rows were removed."""
        count = 0
        for row_id, contact_id in pairs:
            result = cast(
                "CursorResult[Any]",
                await self._session.execute(
                    delete(ContactRowLink).where(
                        ContactRowLink.project_id == project_id,
                        ContactRowLink.row_id == row_id,
                        ContactRowLink.contact_id == contact_id,
                    )
                ),
            )
            count += int(result.rowcount or 0)
        return count
