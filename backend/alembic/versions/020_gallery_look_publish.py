"""gallery items can publish Magic looks (Runway)

Revision ID: 020
Revises: 019
Create Date: 2026-11-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gallery_items",
        sa.Column("look_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_gallery_items_look_id"), "gallery_items", ["look_id"], unique=False)
    op.create_index(
        "uq_gallery_items_look_id",
        "gallery_items",
        ["look_id"],
        unique=True,
        postgresql_where=sa.text("look_id IS NOT NULL"),
    )
    op.alter_column(
        "gallery_items",
        "design_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_gallery_items_design_or_look",
        "gallery_items",
        "design_id IS NOT NULL OR look_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_gallery_items_design_or_look", "gallery_items", type_="check")
    # Rows published from looks cannot survive a NOT NULL design_id restore.
    op.execute("DELETE FROM gallery_items WHERE design_id IS NULL")
    op.alter_column(
        "gallery_items",
        "design_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_index("uq_gallery_items_look_id", table_name="gallery_items")
    op.drop_index(op.f("ix_gallery_items_look_id"), table_name="gallery_items", if_exists=True)
    op.drop_column("gallery_items", "look_id")
