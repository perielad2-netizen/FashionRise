"""Add create_model_upload consent purpose for auditable Create Model agreement.

Revision ID: 036
Revises: 035
Create Date: 2026-11-17

Expands ``user_consent_events.purpose`` CHECK to include ``create_model_upload``
so the complete Create Model short checkbox + seven-point upload agreement can
be recorded with version + notice hash (distinct from adults/storage/AI).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_user_consent_events_purpose", "user_consent_events", type_="check")
    op.create_check_constraint(
        "ck_user_consent_events_purpose",
        "user_consent_events",
        "purpose IN ("
        "'adults_beta', 'croquis_storage', 'croquis_ai_provider', "
        "'try_on_person', 'runway_share', 'croquis_public_share', "
        "'create_model_upload'"
        ")",
    )


def downgrade() -> None:
    count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM user_consent_events WHERE purpose = 'create_model_upload'")
    ).scalar()
    if count and int(count) > 0:
        raise RuntimeError(
            "Cannot downgrade 036 while create_model_upload consent events exist."
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
