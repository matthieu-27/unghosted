"""link analyses table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.projects.id"),
            nullable=False,
        ),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_type", sa.String(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("page_kind", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column(
            "timings_ms", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cleaned_text", sa.Text(), nullable=True),
        sa.Column(
            "raw_output", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
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
    op.create_index(
        "idx_analyses_project", "link_analyses", ["project_id"], schema="app"
    )
    op.create_index("idx_analyses_source", "link_analyses", ["source"], schema="app")


def downgrade() -> None:
    op.drop_index("idx_analyses_source", table_name="link_analyses", schema="app")
    op.drop_index("idx_analyses_project", table_name="link_analyses", schema="app")
    op.drop_table("link_analyses", schema="app")
