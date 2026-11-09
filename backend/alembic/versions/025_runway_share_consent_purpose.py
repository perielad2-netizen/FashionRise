"""Runway share consent purpose allowlist.

Revision ID: 025
Revises: 024
Create Date: 2026-11-08

Expands ``user_consent_events.purpose`` CHECK to include ``runway_share``
(Publish to Runway rights + display permission attestation).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ("
        "'adults_beta', 'croquis_storage', 'croquis_ai_provider', "
        "'try_on_person', 'runway_share'"
        ")",
    )


def downgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM user_consent_events WHERE purpose = 'runway_share'")
    ).scalar()
    if int(count or 0) > 0:
        raise RuntimeError(
            "Cannot downgrade 025 while runway_share consent events exist — "
            "archive or delete those rows first."
        )
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ("
        "'adults_beta', 'croquis_storage', 'croquis_ai_provider', 'try_on_person'"
        ")",
    )
