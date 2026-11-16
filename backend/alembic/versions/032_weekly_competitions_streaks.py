"""Weekly competitions, group awards, login streaks, star payouts.

Revision ID: 032
Revises: 031
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "competition_weeks",
        sa.Column("week_start", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column("week_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "competition_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("week_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["week_start"], ["competition_weeks.week_start"], ondelete="CASCADE"),
        sa.UniqueConstraint("week_start", "group_index", name="uq_competition_groups_week_index"),
    )
    op.create_index("ix_competition_groups_week_start", "competition_groups", ["week_start"])

    op.create_table(
        "competition_group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("week_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["week_start"], ["competition_weeks.week_start"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["competition_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("week_start", "user_id", name="uq_competition_group_members_week_user"),
    )
    op.create_index("ix_competition_group_members_week_start", "competition_group_members", ["week_start"])
    op.create_index("ix_competition_group_members_group_id", "competition_group_members", ["group_id"])
    op.create_index("ix_competition_group_members_user_id", "competition_group_members", ["user_id"])

    op.create_table(
        "competition_awards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("week_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stars_amount", sa.Integer(), nullable=False),
        sa.Column("payout_key", sa.String(length=160), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["week_start"], ["competition_weeks.week_start"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["competition_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gallery_item_id"], ["gallery_items.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "week_start",
            "group_id",
            "category",
            name="uq_competition_awards_week_group_category",
        ),
        sa.UniqueConstraint("payout_key", name="uq_competition_awards_payout_key"),
    )
    op.create_index("ix_competition_awards_week_start", "competition_awards", ["week_start"])
    op.create_index("ix_competition_awards_group_id", "competition_awards", ["group_id"])
    op.create_index("ix_competition_awards_user_id", "competition_awards", ["user_id"])

    op.create_table(
        "star_payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("payout_key", sa.String(length=160), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("payout_key", name="uq_star_payouts_key"),
    )
    op.create_index("ix_star_payouts_user_id", "star_payouts", ["user_id"])

    op.create_table(
        "login_streaks",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checkin_date", sa.Date(), nullable=True),
        sa.Column("lifetime_checkins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("login_streaks")
    op.drop_index("ix_star_payouts_user_id", table_name="star_payouts")
    op.drop_table("star_payouts")
    op.drop_index("ix_competition_awards_user_id", table_name="competition_awards")
    op.drop_index("ix_competition_awards_group_id", table_name="competition_awards")
    op.drop_index("ix_competition_awards_week_start", table_name="competition_awards")
    op.drop_table("competition_awards")
    op.drop_index("ix_competition_group_members_user_id", table_name="competition_group_members")
    op.drop_index("ix_competition_group_members_group_id", table_name="competition_group_members")
    op.drop_index("ix_competition_group_members_week_start", table_name="competition_group_members")
    op.drop_table("competition_group_members")
    op.drop_index("ix_competition_groups_week_start", table_name="competition_groups")
    op.drop_table("competition_groups")
    op.drop_table("competition_weeks")
