"""Create My Croquis Stage A — private assets, consent, versions.

Revision ID: 012
Revises: 011
Create Date: 2026-10-31

Owner-private croquis foundation. Upload/AI gates remain OFF by default.
No provider execution. Retention sweeper is offline/manual only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "private_media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erase_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bytes_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_cleanup_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('croquis_source', 'croquis_generated')",
            name="ck_private_media_assets_kind",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_private_media_assets_storage_key"),
    )
    op.create_index("ix_private_media_assets_owner_id", "private_media_assets", ["owner_id"])
    op.create_index(
        "ix_private_media_assets_cleanup",
        "private_media_assets",
        ["erase_requested_at", "bytes_purged_at"],
    )

    op.create_table(
        "user_consent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("adults_attested", sa.Boolean(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('adults_beta', 'croquis_storage', 'croquis_ai_provider')",
            name="ck_user_consent_events_purpose",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_consent_events_owner_id", "user_consent_events", ["owner_id"])
    op.create_index(
        "ix_user_consent_events_owner_purpose_created",
        "user_consent_events",
        ["owner_id", "purpose", "created_at"],
    )

    op.create_table(
        "personal_croquis",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("storage_consent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("adults_attestation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erase_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_asset_id"], ["private_media_assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["storage_consent_id"], ["user_consent_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_croquis_owner_id", "personal_croquis", ["owner_id"])

    op.create_table(
        "personal_croquis_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("croquis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generated_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ai_consent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_job_id", sa.String(length=128), nullable=True),
        sa.Column("cost_cents", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("geometry_profile", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_personal_croquis_version_ge_1"),
        sa.ForeignKeyConstraint(["croquis_id"], ["personal_croquis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generated_asset_id"],
            ["private_media_assets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_consent_id"], ["user_consent_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "croquis_id",
            "version",
            name="uq_personal_croquis_version_croquis_version",
        ),
    )
    op.create_index("ix_personal_croquis_version_croquis_id", "personal_croquis_version", ["croquis_id"])
    op.create_index("ix_personal_croquis_version_owner_id", "personal_croquis_version", ["owner_id"])
    op.create_index(
        "uq_personal_croquis_version_owner_idempotency",
        "personal_croquis_version",
        ["owner_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # Survives owner cascade so filesystem unlink still has key metadata.
    op.create_table(
        "private_media_cleanup_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_private_media_cleanup_queue_pending",
        "private_media_cleanup_queue",
        ["processed_at", "enqueued_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_private_media_cleanup_queue_pending", table_name="private_media_cleanup_queue")
    op.drop_table("private_media_cleanup_queue")
    op.drop_index(
        "uq_personal_croquis_version_owner_idempotency",
        table_name="personal_croquis_version",
    )
    op.drop_index("ix_personal_croquis_version_owner_id", table_name="personal_croquis_version")
    op.drop_index("ix_personal_croquis_version_croquis_id", table_name="personal_croquis_version")
    op.drop_table("personal_croquis_version")
    op.drop_index("ix_personal_croquis_owner_id", table_name="personal_croquis")
    op.drop_table("personal_croquis")
    op.drop_index("ix_user_consent_events_owner_purpose_created", table_name="user_consent_events")
    op.drop_index("ix_user_consent_events_owner_id", table_name="user_consent_events")
    op.drop_table("user_consent_events")
    op.drop_index("ix_private_media_assets_cleanup", table_name="private_media_assets")
    op.drop_index("ix_private_media_assets_owner_id", table_name="private_media_assets")
    op.drop_table("private_media_assets")
