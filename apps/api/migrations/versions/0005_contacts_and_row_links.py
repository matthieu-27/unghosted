"""contacts, contact_row_links

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.projects.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="app",
    )
    op.create_index("idx_contacts_project", "contacts", ["project_id"], schema="app")
    op.create_index("idx_contacts_email", "contacts", ["email"], schema="app")

    op.create_table(
        "contact_row_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.projects.id"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("contact_id", "row_id"),
        schema="app",
    )
    op.create_index(
        "idx_contact_row_links_project",
        "contact_row_links",
        ["project_id"],
        schema="app",
    )
    op.create_index(
        "idx_contact_row_links_contact",
        "contact_row_links",
        ["contact_id"],
        schema="app",
    )
    op.create_index(
        "idx_contact_row_links_row", "contact_row_links", ["row_id"], schema="app"
    )


def downgrade() -> None:
    op.drop_table("contact_row_links", schema="app")
    op.drop_table("contacts", schema="app")
