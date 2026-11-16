"""Model-level check for croquis-only gallery rows (create_all harness).

The authoritative Alembic upgrade/downgrade regression lives in
``test_alembic_035_gallery_croquis_check.py``.
"""

from __future__ import annotations

from sqlalchemy import text


def test_create_all_model_check_allows_croquis(db_session):
    row = db_session.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'ck_gallery_items_design_look_or_croquis'
            """
        )
    ).scalar()
    assert row is not None
    assert "croquis_id" in row
    assert "design_id" in row
    assert "look_id" in row
