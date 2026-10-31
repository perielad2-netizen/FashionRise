"""PostgreSQL triggers for Create My Croquis version immutability + ownership.

Installed by Alembic 012 and via SQLAlchemy ``after_create`` so ``create_all``
test databases receive the same enforcement as migrated environments.
"""

from __future__ import annotations

from sqlalchemy import DDL, event

from app.models.personal_croquis import PersonalCroquisVersion

# Accepted rows: identity fields cannot change (including generated_asset_id).
# Pre-accept rows may transition status (generating → failed|rejected|accepted)
# and set generated_asset_id once when accepting.
_IMMUTABILITY_FN = """
CREATE OR REPLACE FUNCTION personal_croquis_version_immutability()
RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'accepted' THEN
    IF NEW.generated_asset_id IS DISTINCT FROM OLD.generated_asset_id
       OR NEW.croquis_id IS DISTINCT FROM OLD.croquis_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.status IS DISTINCT FROM OLD.status
       OR NEW.accepted_at IS DISTINCT FROM OLD.accepted_at
       OR NEW.geometry_profile IS DISTINCT FROM OLD.geometry_profile
       OR NEW.prompt_version IS DISTINCT FROM OLD.prompt_version
       OR NEW.ai_consent_id IS DISTINCT FROM OLD.ai_consent_id
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.provider_job_id IS DISTINCT FROM OLD.provider_job_id
       OR NEW.cost_cents IS DISTINCT FROM OLD.cost_cents THEN
      RAISE EXCEPTION 'personal_croquis_version accepted row is immutable'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_OWNERSHIP_FN = """
CREATE OR REPLACE FUNCTION personal_croquis_version_owner_consistency()
RETURNS trigger AS $$
DECLARE
  croquis_owner UUID;
  asset_owner UUID;
BEGIN
  SELECT owner_id INTO croquis_owner FROM personal_croquis WHERE id = NEW.croquis_id;
  IF croquis_owner IS NULL THEN
    RAISE EXCEPTION 'personal_croquis_version croquis_id not found'
      USING ERRCODE = 'foreign_key_violation';
  END IF;
  IF croquis_owner IS DISTINCT FROM NEW.owner_id THEN
    RAISE EXCEPTION 'personal_croquis_version owner_id must match personal_croquis.owner_id'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF NEW.generated_asset_id IS NOT NULL THEN
    SELECT owner_id INTO asset_owner FROM private_media_assets WHERE id = NEW.generated_asset_id;
    IF asset_owner IS NULL THEN
      RAISE EXCEPTION 'personal_croquis_version generated_asset_id not found'
        USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF asset_owner IS DISTINCT FROM NEW.owner_id THEN
      RAISE EXCEPTION 'personal_croquis_version generated_asset must be owned by same user'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END IF;
  IF NEW.status = 'accepted' AND NEW.generated_asset_id IS NULL THEN
    RAISE EXCEPTION 'accepted personal_croquis_version requires generated_asset_id'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

INSTALL_TRIGGERS_SQL = f"""
{_IMMUTABILITY_FN}
{_OWNERSHIP_FN}
DROP TRIGGER IF EXISTS trg_personal_croquis_version_immutability ON personal_croquis_version;
CREATE TRIGGER trg_personal_croquis_version_immutability
  BEFORE UPDATE ON personal_croquis_version
  FOR EACH ROW EXECUTE PROCEDURE personal_croquis_version_immutability();
DROP TRIGGER IF EXISTS trg_personal_croquis_version_owner_consistency ON personal_croquis_version;
CREATE TRIGGER trg_personal_croquis_version_owner_consistency
  BEFORE INSERT OR UPDATE ON personal_croquis_version
  FOR EACH ROW EXECUTE PROCEDURE personal_croquis_version_owner_consistency();
"""

DROP_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS trg_personal_croquis_version_immutability ON personal_croquis_version;
DROP TRIGGER IF EXISTS trg_personal_croquis_version_owner_consistency ON personal_croquis_version;
DROP FUNCTION IF EXISTS personal_croquis_version_immutability();
DROP FUNCTION IF EXISTS personal_croquis_version_owner_consistency();
"""


def register_personal_croquis_ddl() -> None:
    """Attach after_create / before_drop listeners (idempotent)."""
    if getattr(register_personal_croquis_ddl, "_registered", False):
        return
    event.listen(
        PersonalCroquisVersion.__table__,
        "after_create",
        DDL(INSTALL_TRIGGERS_SQL).execute_if(dialect="postgresql"),
    )
    event.listen(
        PersonalCroquisVersion.__table__,
        "before_drop",
        DDL(DROP_TRIGGERS_SQL).execute_if(dialect="postgresql"),
    )
    register_personal_croquis_ddl._registered = True  # type: ignore[attr-defined]


register_personal_croquis_ddl()
