"""Personal croquis male/female sex flag for Try On Person.

Revision ID: 041
Revises: 040
Create Date: 2026-11-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "personal_croquis",
        sa.Column("sex", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_personal_croquis_sex",
        "personal_croquis",
        "sex IS NULL OR sex IN ('male', 'female')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_personal_croquis_sex", "personal_croquis", type_="check")
    op.drop_column("personal_croquis", "sex")
