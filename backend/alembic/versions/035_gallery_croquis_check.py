"""Allow croquis-only gallery rows (My Models publish).

Revision ID: 035
Revises: 034
Create Date: 2026-11-16

Migration 033 added ``gallery_items.croquis_id`` for My Models → FashionRise
publish, but left ``ck_gallery_items_design_or_look`` requiring ``design_id`` or
``look_id``. Alembic-migrated databases therefore rejected croquis-only rows
(SQLAlchemy ``create_all`` test DBs never had the check, so unit tests missed it).

Replace the check so a gallery item must have at least one of
``design_id``, ``look_id``, or ``croquis_id``.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_gallery_items_design_or_look", "gallery_items", type_="check")
    op.create_check_constraint(
        "ck_gallery_items_design_look_or_croquis",
        "gallery_items",
        "design_id IS NOT NULL OR look_id IS NOT NULL OR croquis_id IS NOT NULL",
    )


def downgrade() -> None:
    # Rows that only have croquis_id cannot satisfy the pre-035 check.
    op.execute("DELETE FROM gallery_items WHERE design_id IS NULL AND look_id IS NULL")
    op.drop_constraint(
        "ck_gallery_items_design_look_or_croquis", "gallery_items", type_="check"
    )
    op.create_check_constraint(
        "ck_gallery_items_design_or_look",
        "gallery_items",
        "design_id IS NOT NULL OR look_id IS NOT NULL",
    )
