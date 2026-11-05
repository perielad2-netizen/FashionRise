"""Personal Try On Person — consent purpose allowlist.

Revision ID: 015
Revises: 014
Create Date: 2026-11-01

Expands ``user_consent_events.purpose`` CHECK to include ``try_on_person``.
No new tables — try-on jobs reuse ``ai_jobs`` + LocalStorage look images and
``personal_croquis_spend_reservations`` for spend fencing.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ('adults_beta', 'croquis_storage', 'croquis_ai_provider', 'try_on_person')",
    )


def downgrade() -> None:
    # Refuse downgrade while try-on consent rows exist.
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM user_consent_events WHERE purpose = 'try_on_person'")
    ).scalar()
    if int(count or 0) > 0:
        raise RuntimeError(
            "Cannot downgrade 015 while try_on_person consent events exist — "
            "archive or delete those rows first."
        )
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ('adults_beta', 'croquis_storage', 'croquis_ai_provider')",
    )
