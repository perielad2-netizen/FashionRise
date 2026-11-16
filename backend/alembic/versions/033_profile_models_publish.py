"""Gallery croquis publish + croquis_public_share consent purpose.

Revision ID: 033
Revises: 032
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gallery_items",
        sa.Column(
            "croquis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("personal_croquis.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_gallery_items_croquis_id", "gallery_items", ["croquis_id"])
    op.create_index(
        "uq_gallery_items_croquis_id",
        "gallery_items",
        ["croquis_id"],
        unique=True,
        postgresql_where=sa.text("croquis_id IS NOT NULL"),
    )

    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ("
        "'adults_beta', 'croquis_storage', 'croquis_ai_provider', "
        "'try_on_person', 'runway_share', 'croquis_public_share'"
        ")",
    )


def downgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM user_consent_events WHERE purpose = 'croquis_public_share'"
        )
    ).scalar()
    if int(count or 0) > 0:
        raise RuntimeError(
            "Cannot downgrade 033 while croquis_public_share consent events exist."
        )
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ("
        "'adults_beta', 'croquis_storage', 'croquis_ai_provider', "
        "'try_on_person', 'runway_share'"
        ")",
    )
    op.drop_index("uq_gallery_items_croquis_id", table_name="gallery_items")
    op.drop_index("ix_gallery_items_croquis_id", table_name="gallery_items")
    op.drop_column("gallery_items", "croquis_id")
