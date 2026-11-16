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

Downgrade is **non-destructive**: if any gallery row depends exclusively on
``croquis_id`` (no ``design_id`` / ``look_id``), refuse with ``RuntimeError``
rather than deleting published My Models or related engagement.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
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
    """Restore the pre-035 check only when no croquis-only gallery rows exist."""
    bind = op.get_bind()
    croquis_only = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM gallery_items
            WHERE croquis_id IS NOT NULL
              AND design_id IS NULL
              AND look_id IS NULL
            """
        )
    ).scalar()
    croquis_only = int(croquis_only or 0)
    if croquis_only > 0:
        raise RuntimeError(
            "Refusing Alembic downgrade 035 → 034: "
            f"{croquis_only} gallery_items row(s) depend exclusively on croquis_id "
            "(published My Models). Automatic DELETE is forbidden — it would destroy "
            "valid gallery rows and associated likes/comments/ratings/impressions/"
            "public images. Downgrade requires an explicit, separately authorized "
            "data migration before restoring ck_gallery_items_design_or_look."
        )

    op.drop_constraint(
        "ck_gallery_items_design_look_or_croquis", "gallery_items", type_="check"
    )
    op.create_check_constraint(
        "ck_gallery_items_design_or_look",
        "gallery_items",
        "design_id IS NOT NULL OR look_id IS NOT NULL",
    )
