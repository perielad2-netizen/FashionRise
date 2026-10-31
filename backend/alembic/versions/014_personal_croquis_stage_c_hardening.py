"""Create My Croquis Stage C P0 hardening — spend ledger + AI consent binding.

Revision ID: 014
Revises: 013
Create Date: 2026-10-31

- Preserve anonymized spend rows when owner/croquis deleted (SET NULL FKs).
- Append-only AI consent ↔ croquis/source binding.
- Worker claim lease columns on AI jobs for croquis crash recovery.
Disposable only — not applied in production until authorized.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Spend reservation: keep cost history after owner/croquis deletion ---
    op.alter_column(
        "personal_croquis_spend_reservations",
        "owner_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "personal_croquis_spend_reservations",
        "croquis_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.drop_constraint(
        "personal_croquis_spend_reservations_owner_id_fkey",
        "personal_croquis_spend_reservations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "personal_croquis_spend_reservations_croquis_id_fkey",
        "personal_croquis_spend_reservations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "personal_croquis_spend_reservations_owner_id_fkey",
        "personal_croquis_spend_reservations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "personal_croquis_spend_reservations_croquis_id_fkey",
        "personal_croquis_spend_reservations",
        "personal_croquis",
        ["croquis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "personal_croquis_spend_reservations",
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "personal_croquis_spend_reservations",
        sa.Column(
            "max_exposure_cents",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_personal_croquis_spend_source_status",
        "personal_croquis_spend_reservations",
        ["source_asset_id", "status"],
    )

    # --- AI consent binding (append-only scope to croquis + source) ---
    op.create_table(
        "personal_croquis_ai_consent_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("croquis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notice_version", sa.String(length=64), nullable=False),
        sa.Column("notice_text_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["consent_id"], ["user_consent_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["croquis_id"], ["personal_croquis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_asset_id"], ["private_media_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consent_id",
            "croquis_id",
            "source_asset_id",
            name="uq_personal_croquis_ai_consent_binding_scope",
        ),
    )
    op.create_index(
        "ix_personal_croquis_ai_consent_bindings_owner_id",
        "personal_croquis_ai_consent_bindings",
        ["owner_id"],
    )

    # --- Worker lease fields on AI jobs (used by croquis generate) ---
    op.add_column(
        "ai_jobs",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_jobs",
        sa.Column("claim_token", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_jobs", "claim_token")
    op.drop_column("ai_jobs", "claimed_at")
    op.drop_index(
        "ix_personal_croquis_ai_consent_bindings_owner_id",
        table_name="personal_croquis_ai_consent_bindings",
    )
    op.drop_table("personal_croquis_ai_consent_bindings")
    op.drop_index(
        "ix_personal_croquis_spend_source_status",
        table_name="personal_croquis_spend_reservations",
    )
    op.drop_column("personal_croquis_spend_reservations", "max_exposure_cents")
    op.drop_column("personal_croquis_spend_reservations", "source_asset_id")
    op.drop_constraint(
        "personal_croquis_spend_reservations_croquis_id_fkey",
        "personal_croquis_spend_reservations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "personal_croquis_spend_reservations_owner_id_fkey",
        "personal_croquis_spend_reservations",
        type_="foreignkey",
    )
    op.alter_column(
        "personal_croquis_spend_reservations",
        "croquis_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.alter_column(
        "personal_croquis_spend_reservations",
        "owner_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "personal_croquis_spend_reservations_owner_id_fkey",
        "personal_croquis_spend_reservations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "personal_croquis_spend_reservations_croquis_id_fkey",
        "personal_croquis_spend_reservations",
        "personal_croquis",
        ["croquis_id"],
        ["id"],
        ondelete="CASCADE",
    )
