"""registration_invitations for invite-only beta signup

Revision ID: 004
Revises: 003
Create Date: 2026-10-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registration_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_registration_invitations_email_normalized",
        "registration_invitations",
        ["email_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_registration_invitations_token_hash",
        "registration_invitations",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_registration_invitations_token_hash", table_name="registration_invitations", if_exists=True)
    op.drop_index(
        "ix_registration_invitations_email_normalized",
        table_name="registration_invitations",
        if_exists=True,
    )
    op.drop_table("registration_invitations", if_exists=True)
