"""documents, document_texts, applicant_profiles, consents

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.projects.id"),
            nullable=False,
        ),
        sa.Column("type_key", sa.String(), nullable=False),
        sa.Column("model_eligible", sa.Boolean(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("encrypted_data_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_algorithm_version", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("retention_date", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("project_id", "storage_key"),
        schema="app",
    )
    op.create_index("idx_documents_project", "documents", ["project_id"], schema="app")

    op.create_table(
        "document_texts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.documents.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("document_id"),
        schema="app",
    )
    op.create_index(
        "idx_document_texts_document", "document_texts", ["document_id"], schema="app"
    )

    op.create_table(
        "applicant_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.projects.id"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("seeking", sa.Text(), nullable=True),
        sa.Column(
            "highlights", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("motivation", sa.Text(), nullable=True),
        sa.Column(
            "style_notes", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("project_id", "version_number"),
        schema="app",
    )
    op.create_index(
        "idx_profiles_project", "applicant_profiles", ["project_id"], schema="app"
    )

    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("user_id", "kind"),
        schema="app",
    )
    op.create_index("idx_consents_user", "consents", ["user_id"], schema="app")


def downgrade() -> None:
    op.drop_index("idx_consents_user", table_name="consents", schema="app")
    op.drop_table("consents", schema="app")
    op.drop_index("idx_profiles_project", table_name="applicant_profiles", schema="app")
    op.drop_table("applicant_profiles", schema="app")
    op.drop_index(
        "idx_document_texts_document", table_name="document_texts", schema="app"
    )
    op.drop_table("document_texts", schema="app")
    op.drop_index("idx_documents_project", table_name="documents", schema="app")
    op.drop_table("documents", schema="app")
