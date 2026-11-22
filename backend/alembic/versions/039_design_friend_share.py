"""Design share-with-friend collaborations + asset grants.

Revision ID: 039
Revises: 038
Create Date: 2026-11-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "design_collaborations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_low_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_high_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "origin_design_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("garment_designs.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_design_collaborations_pair"),
        sa.CheckConstraint("user_low_id <> user_high_id", name="ck_design_collaborations_not_self"),
    )
    op.create_index("ix_design_collaborations_user_low_id", "design_collaborations", ["user_low_id"])
    op.create_index("ix_design_collaborations_user_high_id", "design_collaborations", ["user_high_id"])

    op.create_table(
        "design_share_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "collaboration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("design_collaborations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_design_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("garment_designs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "received_design_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("garment_designs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_design_share_transfers_collaboration_id",
        "design_share_transfers",
        ["collaboration_id"],
    )
    op.create_index(
        "ix_design_share_transfers_to_user_id",
        "design_share_transfers",
        ["to_user_id"],
    )

    op.create_table(
        "shared_asset_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "collaboration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("design_collaborations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "granter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grantee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_kind", sa.String(length=16), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "collaboration_id",
            "grantee_id",
            "asset_kind",
            "asset_id",
            name="uq_shared_asset_grants_target",
        ),
        sa.CheckConstraint(
            "asset_kind IN ('fabric', 'croquis')",
            name="ck_shared_asset_grants_kind",
        ),
        sa.CheckConstraint("granter_id <> grantee_id", name="ck_shared_asset_grants_not_self"),
    )
    op.create_index("ix_shared_asset_grants_grantee_id", "shared_asset_grants", ["grantee_id"])
    op.create_index(
        "ix_shared_asset_grants_asset",
        "shared_asset_grants",
        ["asset_kind", "asset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_shared_asset_grants_asset", table_name="shared_asset_grants")
    op.drop_index("ix_shared_asset_grants_grantee_id", table_name="shared_asset_grants")
    op.drop_table("shared_asset_grants")
    op.drop_index("ix_design_share_transfers_to_user_id", table_name="design_share_transfers")
    op.drop_index("ix_design_share_transfers_collaboration_id", table_name="design_share_transfers")
    op.drop_table("design_share_transfers")
    op.drop_index("ix_design_collaborations_user_high_id", table_name="design_collaborations")
    op.drop_index("ix_design_collaborations_user_low_id", table_name="design_collaborations")
    op.drop_table("design_collaborations")
