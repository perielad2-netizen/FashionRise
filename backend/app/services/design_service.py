import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.models.color_palette import ColorPalette
from app.models.design_revision import DesignRevision
from app.models.garment_design import GarmentDesign
from app.models.garment_template import GarmentTemplate
from app.models.material_definition import MaterialDefinition
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.design import DesignCreate, DesignRead, DesignUpdate
from app.schemas.export import ExportCreate
from app.services import export_service
from app.storage.local import LocalStorageBackend

STUDIO_DRAFT_KIND = "studio_working_draft"
STUDIO_DRAFT_V1 = "fashionrise.studio.draft.v1"
STUDIO_DRAFT_V2 = "fashionrise.studio.draft.v2"
STUDIO_DRAFT_SCHEMAS = frozenset({STUDIO_DRAFT_V1, STUDIO_DRAFT_V2})
SAVED_DESIGN_KIND = "saved_design"
SAVED_DESIGN_V1 = "fashionrise.saved_design.v1"
SAVED_DESIGN_V2 = "fashionrise.saved_design.v2"
SAVED_DESIGN_SCHEMAS = frozenset({SAVED_DESIGN_V1, SAVED_DESIGN_V2})


def _assert_owner(design: GarmentDesign, user: User) -> None:
    if design.user_id != user.id:
        raise ForbiddenError("Not allowed to modify this design")


def _studio_client_revision(design: GarmentDesign) -> int:
    return _client_revision_from_payloads(design.metadata_ or {}, design.design_data or {})


def _client_revision_from_payloads(*sources: dict[str, Any]) -> int:
    for source in sources:
        raw = source.get("clientRevision")
        if isinstance(raw, int) and raw >= 0:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    return 0


def _is_studio_schema(schema: Any) -> bool:
    return isinstance(schema, str) and schema in STUDIO_DRAFT_SCHEMAS


def _is_saved_schema(schema: Any) -> bool:
    return isinstance(schema, str) and schema in SAVED_DESIGN_SCHEMAS


def _is_studio_working_draft(design: GarmentDesign) -> bool:
    meta = design.metadata_ or {}
    data = design.design_data or {}
    return meta.get("draftKind") == STUDIO_DRAFT_KIND or _is_studio_schema(data.get("schema"))


def _is_studio_payload(meta: dict[str, Any] | None, design_data: dict[str, Any] | None) -> bool:
    meta = meta or {}
    design_data = design_data or {}
    return meta.get("draftKind") == STUDIO_DRAFT_KIND or _is_studio_schema(design_data.get("schema"))


def _is_saved_design_payload(meta: dict[str, Any] | None, design_data: dict[str, Any] | None) -> bool:
    meta = meta or {}
    design_data = design_data or {}
    return meta.get("designKind") == SAVED_DESIGN_KIND or _is_saved_schema(design_data.get("schema"))


def _is_saved_design_row(design: GarmentDesign) -> bool:
    return _is_saved_design_payload(design.metadata_ or {}, design.design_data or {})


def _normalize_fill_list(fills: Any) -> list[Any]:
    if fills is None:
        return []
    if not isinstance(fills, list):
        return []
    return fills


def _normalize_studio_fills(design_data: dict[str, Any] | None) -> list[Any]:
    """Normalize garment fills for fingerprinting.

    Older Studio V1 drafts omit `fills`; treat missing and empty `[]` as equivalent
    so legacy reopen/retry stays idempotent while fill-only edits still advance.
    """
    data = design_data or {}
    return _normalize_fill_list(data.get("fills", []))


def _normalize_active_side(design_data: dict[str, Any] | None) -> str:
    data = design_data or {}
    side = data.get("activeSide")
    if side in ("front", "back"):
        return side
    return "front"


def _normalize_back_sentinel(design_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Absent `back` key → None; present bag → normalized strokes/fills.

    Absent and intentionally empty bags MUST fingerprint differently.
    """
    data = design_data or {}
    if "back" not in data:
        return None
    back = data.get("back")
    if not isinstance(back, dict):
        return {"strokes": [], "fills": []}
    return {
        "strokes": back.get("strokes") if isinstance(back.get("strokes"), list) else [],
        "fills": _normalize_fill_list(back.get("fills", [])),
    }


def _studio_content_fingerprint(design_data: dict[str, Any] | None) -> str:
    data = design_data or {}
    schema = data.get("schema")
    if not _is_studio_schema(schema):
        schema = STUDIO_DRAFT_V1 if schema is None else schema
    payload = {
        "schema": schema,
        "strokes": data.get("strokes"),
        "fills": _normalize_studio_fills(data),
        "model": data.get("model"),
        "customReferenceUrl": data.get("customReferenceUrl"),
        "customReferenceKey": data.get("customReferenceKey"),
        "brush": data.get("brush"),
        "dimmed": data.get("dimmed"),
        "activeSide": _normalize_active_side(data),
        "back": _normalize_back_sentinel(data),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _saved_snapshot_fingerprint(design_data: dict[str, Any] | None) -> str:
    data = design_data or {}
    raw_snapshot = data.get("snapshot")
    snapshot: dict[str, Any] = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    payload = {
        "schema": data.get("schema"),
        "saveRequestId": data.get("saveRequestId"),
        "snapshot": {
            "strokes": snapshot.get("strokes"),
            "fills": _normalize_fill_list(snapshot.get("fills", [])),
            "model": snapshot.get("model"),
            "brush": snapshot.get("brush"),
            "dimmed": snapshot.get("dimmed"),
            "activeSide": _normalize_active_side(snapshot),
            "back": _normalize_back_sentinel(snapshot),
        },
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _has_back_key(design_data: dict[str, Any] | None) -> bool:
    return isinstance(design_data, dict) and "back" in design_data


def _is_two_sided_studio(design_data: dict[str, Any] | None) -> bool:
    data = design_data or {}
    return data.get("schema") == STUDIO_DRAFT_V2 or _has_back_key(data)


def _validate_side_bag(bag: Any, *, field_name: str) -> None:
    if not isinstance(bag, dict):
        raise ValidationAppError(f"{field_name} must be an object")
    if "strokes" in bag and not isinstance(bag.get("strokes"), list):
        raise ValidationAppError(f"{field_name}.strokes must be an array")
    if "fills" in bag and bag.get("fills") is not None and not isinstance(bag.get("fills"), list):
        raise ValidationAppError(f"{field_name}.fills must be an array")


def _validate_studio_design_data(design_data: dict[str, Any] | None) -> None:
    data = design_data or {}
    schema = data.get("schema")
    if schema is None:
        raise ValidationAppError("Studio draft schema is required")
    if not _is_studio_schema(schema):
        raise ValidationAppError("Unsupported Studio draft schema")
    if "activeSide" in data and data.get("activeSide") not in ("front", "back"):
        raise ValidationAppError("activeSide must be 'front' or 'back'")
    if schema == STUDIO_DRAFT_V1 and _has_back_key(data):
        raise ValidationAppError("fashionrise.studio.draft.v1 must not include a back key")
    if schema == STUDIO_DRAFT_V2 and _has_back_key(data):
        _validate_side_bag(data.get("back"), field_name="back")


def _validate_saved_design_data(design_data: dict[str, Any] | None) -> None:
    data = design_data or {}
    schema = data.get("schema")
    if not _is_saved_schema(schema):
        raise ValidationAppError("Unsupported saved design schema")
    snapshot = data.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValidationAppError("saved design snapshot must be an object")
    if "activeSide" in snapshot and snapshot.get("activeSide") not in ("front", "back"):
        raise ValidationAppError("snapshot.activeSide must be 'front' or 'back'")
    if schema == SAVED_DESIGN_V1 and _has_back_key(snapshot):
        raise ValidationAppError("fashionrise.saved_design.v1 snapshot must not include a back key")
    if schema == SAVED_DESIGN_V2 and _has_back_key(snapshot):
        _validate_side_bag(snapshot.get("back"), field_name="snapshot.back")


def _studio_downgrade_reason(
    stored: dict[str, Any] | None, incoming: dict[str, Any] | None
) -> str | None:
    """Return a stable reason code when incoming would strip/downgrade two-sided data."""
    stored_data = stored or {}
    incoming_data = incoming or {}
    if stored_data.get("schema") == STUDIO_DRAFT_V2 and incoming_data.get("schema") == STUDIO_DRAFT_V1:
        return "studio_schema_downgrade"
    if _has_back_key(stored_data) and not _has_back_key(incoming_data):
        return "back_stripped"
    return None


def _saved_downgrade_reason(
    stored: dict[str, Any] | None, incoming: dict[str, Any] | None
) -> str | None:
    stored_data = stored or {}
    incoming_data = incoming or {}
    if stored_data.get("schema") == SAVED_DESIGN_V2 and incoming_data.get("schema") == SAVED_DESIGN_V1:
        return "saved_schema_downgrade"
    stored_snap = stored_data.get("snapshot") if isinstance(stored_data.get("snapshot"), dict) else {}
    incoming_snap = incoming_data.get("snapshot") if isinstance(incoming_data.get("snapshot"), dict) else {}
    if _has_back_key(stored_snap) and not _has_back_key(incoming_snap):
        return "back_stripped"
    return None


def _capability_sides(meta: dict[str, Any] | None) -> int | None:
    meta = meta or {}
    raw = meta.get("studioSides")
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _save_request_id(meta: dict[str, Any] | None, design_data: dict[str, Any] | None) -> str | None:
    meta = meta or {}
    design_data = design_data or {}
    for source in (design_data, meta):
        raw = source.get("saveRequestId")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _studio_lock_key(user_id: uuid.UUID) -> int:
    """Stable signed 64-bit advisory lock key for per-owner Studio draft creation."""
    return int.from_bytes(user_id.bytes[:8], "big", signed=True)


def _conflict_payload(design: GarmentDesign, expected_revision: int | None) -> dict[str, Any]:
    return {
        "expected_revision": expected_revision,
        "current_revision": _studio_client_revision(design),
        "design": DesignRead.model_validate(design).model_dump(mode="json", by_alias=True),
    }


def _reject_capability_downgrade(
    *,
    stored: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    incoming_meta: dict[str, Any] | None,
    conflict_design: GarmentDesign,
    expected_revision: int | None,
) -> None:
    sides = _capability_sides(incoming_meta)
    if sides is None:
        return
    if sides < 2 and (_is_two_sided_studio(stored) or _is_two_sided_studio(incoming)):
        raise ConflictError(
            "Client capability cannot overwrite a two-sided Studio draft.",
            payload={
                **_conflict_payload(conflict_design, expected_revision),
                "reason": "studio_sides_insufficient",
            },
        )


def _raise_studio_downgrade(
    reason: str,
    design: GarmentDesign,
    expected_revision: int | None,
) -> None:
    messages = {
        "studio_schema_downgrade": "Cannot downgrade a Studio draft.v2 document to draft.v1.",
        "back_stripped": "Cannot strip Back artwork from a Studio working draft.",
        "studio_sides_insufficient": "Client capability cannot overwrite a two-sided Studio draft.",
    }
    raise ConflictError(
        messages.get(reason, "Studio draft downgrade rejected."),
        payload={
            **_conflict_payload(design, expected_revision),
            "reason": reason,
        },
    )


def _raise_saved_downgrade(reason: str, design: GarmentDesign) -> None:
    messages = {
        "saved_schema_downgrade": "Cannot rewrite a saved_design.v2 envelope as v1.",
        "back_stripped": "Cannot strip Back artwork from a saved design.",
    }
    raise ConflictError(
        messages.get(reason, "Saved design downgrade rejected."),
        payload={
            "reason": reason,
            "design": DesignRead.model_validate(design).model_dump(mode="json", by_alias=True),
        },
    )


def find_saved_design_by_request_id(db: Session, user: User, save_request_id: str) -> GarmentDesign | None:
    rows = list(
        db.scalars(
            select(GarmentDesign)
            .where(GarmentDesign.user_id == user.id, GarmentDesign.visibility == "private")
            .order_by(GarmentDesign.created_at.desc())
        ).all()
    )
    for row in rows:
        if not _is_saved_design_row(row):
            continue
        existing_id = _save_request_id(row.metadata_ or {}, row.design_data or {})
        if existing_id == save_request_id:
            return row
    return None


def find_studio_working_draft(db: Session, user: User) -> GarmentDesign | None:
    """Return the newest owner-scoped Studio working draft, if any."""
    rows = list(
        db.scalars(
            select(GarmentDesign)
            .where(GarmentDesign.user_id == user.id, GarmentDesign.visibility == "private")
            .order_by(GarmentDesign.updated_at.desc())
        ).all()
    )
    for row in rows:
        if _is_studio_working_draft(row):
            return row
    return None


def create_design(db: Session, user: User, data: DesignCreate) -> GarmentDesign:
    # Reconcile Studio working drafts so a lost POST response cannot spawn duplicates.
    meta = data.metadata or {}
    design_data = data.design_data or {}
    is_studio = _is_studio_payload(meta, design_data)
    is_saved = _is_saved_design_payload(meta, design_data)

    if is_studio:
        _validate_studio_design_data(design_data)
    elif is_saved:
        _validate_saved_design_data(design_data)

    if is_studio and data.visibility == "private":
        # Serialize create/reconcile per owner so concurrent POSTs cannot insert duplicates.
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _studio_lock_key(user.id)})
        existing = find_studio_working_draft(db, user)
        if existing:
            incoming_rev = _client_revision_from_payloads(meta, design_data)
            current_rev = _studio_client_revision(existing)
            # Downgrade rejection MUST run before identical/stale shortcuts so an old PWA
            # never receives a silent success that hides Back artwork loss.
            reason = _studio_downgrade_reason(existing.design_data, design_data)
            if reason:
                _raise_studio_downgrade(reason, existing, incoming_rev)
            _reject_capability_downgrade(
                stored=existing.design_data,
                incoming=design_data,
                incoming_meta=meta,
                conflict_design=existing,
                expected_revision=incoming_rev,
            )
            same_content = _studio_content_fingerprint(existing.design_data) == _studio_content_fingerprint(
                design_data
            )
            # Identical retry (any revision relationship) is idempotent.
            if same_content:
                return existing
            # Never clobber a newer concurrent save with a stale create retry.
            if incoming_rev < current_rev:
                return existing
            # Different content at the same or higher revision must not silently overwrite.
            # Concurrent first creates (and reopen-into-empty) use PUT+OCC when they already
            # know the draft id; create/reconcile only preserves or conflicts.
            raise ConflictError(
                "Studio working draft already exists with different content.",
                payload=_conflict_payload(existing, incoming_rev),
            )
    elif is_saved and data.visibility == "private":
        request_id = _save_request_id(meta, design_data)
        if request_id:
            existing_saved = find_saved_design_by_request_id(db, user, request_id)
            if existing_saved:
                reason = _saved_downgrade_reason(existing_saved.design_data, design_data)
                if reason:
                    _raise_saved_downgrade(reason, existing_saved)
                if _saved_snapshot_fingerprint(existing_saved.design_data) == _saved_snapshot_fingerprint(
                    design_data
                ):
                    return existing_saved
                raise ConflictError(
                    "Saved design saveRequestId already used with different content.",
                    payload={
                        "reason": "saved_request_conflict",
                        "design": DesignRead.model_validate(existing_saved).model_dump(
                            mode="json", by_alias=True
                        ),
                    },
                )

    d = GarmentDesign(
        user_id=user.id,
        title=data.title,
        description=data.description,
        garment_category=data.garment_category,
        template_id=data.template_id,
        material_id=data.material_id,
        color_palette_id=data.color_palette_id,
        design_data=data.design_data,
        metadata_=data.metadata,
        visibility=data.visibility,
        status=data.status,
    )
    db.add(d)
    db.flush()
    _bump_design_count(db, user.id, 1)
    db.commit()
    db.refresh(d)
    return d


def list_my_designs(db: Session, user: User) -> list[GarmentDesign]:
    return list(
        db.scalars(
            select(GarmentDesign).where(GarmentDesign.user_id == user.id).order_by(GarmentDesign.created_at.desc())
        ).all()
    )


def get_design(db: Session, design_id: uuid.UUID, user: User | None) -> GarmentDesign:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    if user and d.user_id == user.id:
        return d
    if d.visibility == "public" and d.moderation_status == "ok":
        return d
    raise NotFoundError("Design not found")


def update_design(db: Session, design_id: uuid.UUID, user: User, data: DesignUpdate) -> GarmentDesign:
    # Row lock prevents two concurrent Studio writers from both passing a stale
    # revision check against the same snapshot.
    d = db.execute(
        select(GarmentDesign).where(GarmentDesign.id == design_id).with_for_update()
    ).scalar_one_or_none()
    if not d:
        raise NotFoundError("Design not found")
    _assert_owner(d, user)

    incoming_meta = data.metadata if data.metadata is not None else (d.metadata_ or {})
    incoming_data = data.design_data if data.design_data is not None else (d.design_data or {})
    touches_studio = _is_studio_working_draft(d) or _is_studio_payload(incoming_meta, incoming_data)
    touches_saved = _is_saved_design_row(d) or _is_saved_design_payload(incoming_meta, incoming_data)

    if touches_studio:
        if data.design_data is not None:
            _validate_studio_design_data(data.design_data)
        if data.expected_revision is None:
            raise ConflictError(
                "expected_revision is required when updating a Studio working draft.",
                payload=_conflict_payload(d, None),
            )
        current_revision = _studio_client_revision(d)
        if current_revision != data.expected_revision:
            # Still reject downgrade attempts even on stale expected_revision so clients
            # never treat a conflict payload as permission to strip Back later.
            if data.design_data is not None:
                reason = _studio_downgrade_reason(d.design_data, data.design_data)
                if reason:
                    _raise_studio_downgrade(reason, d, data.expected_revision)
            raise ConflictError(
                "Draft was updated elsewhere. Resolve the conflict before saving again.",
                payload=_conflict_payload(d, data.expected_revision),
            )
        if data.design_data is not None:
            incoming_rev = _client_revision_from_payloads(incoming_meta, incoming_data)
            reason = _studio_downgrade_reason(d.design_data, data.design_data)
            if reason:
                _raise_studio_downgrade(reason, d, data.expected_revision)
            _reject_capability_downgrade(
                stored=d.design_data,
                incoming=data.design_data,
                incoming_meta=incoming_meta,
                conflict_design=d,
                expected_revision=data.expected_revision,
            )
            same_content = _studio_content_fingerprint(d.design_data) == _studio_content_fingerprint(
                data.design_data
            )
            if incoming_rev < current_revision:
                raise ConflictError(
                    "Studio draft revision is stale and cannot overwrite newer work.",
                    payload=_conflict_payload(d, data.expected_revision),
                )
            if incoming_rev == current_revision and not same_content:
                raise ConflictError(
                    "Studio draft revision must advance when content changes.",
                    payload=_conflict_payload(d, data.expected_revision),
                )
            if same_content:
                # Idempotent retry — acknowledge without rewriting.
                return d
    elif touches_saved:
        if data.design_data is not None:
            _validate_saved_design_data(data.design_data)
            reason = _saved_downgrade_reason(d.design_data, data.design_data)
            if reason:
                _raise_saved_downgrade(reason, d)
            # Named saves are immutable for envelope/content identity; identical retries OK.
            if _saved_snapshot_fingerprint(d.design_data) == _saved_snapshot_fingerprint(data.design_data):
                return d
            raise ConflictError(
                "Saved designs are immutable; create a new save instead of rewriting content.",
                payload={
                    "reason": "saved_design_immutable",
                    "design": DesignRead.model_validate(d).model_dump(mode="json", by_alias=True),
                },
            )
    elif data.expected_revision is not None:
        current_revision = _studio_client_revision(d)
        if current_revision != data.expected_revision:
            raise ConflictError(
                "Draft was updated elsewhere. Resolve the conflict before saving again.",
                payload=_conflict_payload(d, data.expected_revision),
            )

    if data.title is not None:
        d.title = data.title
    if data.description is not None:
        d.description = data.description
    if data.garment_category is not None:
        d.garment_category = data.garment_category
    if data.template_id is not None:
        d.template_id = data.template_id
    if data.material_id is not None:
        d.material_id = data.material_id
    if data.color_palette_id is not None:
        d.color_palette_id = data.color_palette_id
    if data.design_data is not None:
        d.design_data = data.design_data
    if data.metadata is not None:
        d.metadata_ = data.metadata
    if data.visibility is not None:
        d.visibility = data.visibility
    if data.status is not None:
        d.status = data.status
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def delete_design(db: Session, design_id: uuid.UUID, user: User) -> None:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    _assert_owner(d, user)
    db.delete(d)
    _bump_design_count(db, user.id, -1)
    db.commit()


def _owned_design(db: Session, design_id: uuid.UUID, user: User) -> GarmentDesign:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    _assert_owner(d, user)
    return d


def build_handoff_manifest(db: Session, design_id: uuid.UUID, user: User) -> dict[str, Any]:
    """Owner-only JSON bundle for maker / atelier handoff (spec + catalog refs + design_data)."""
    d = _owned_design(db, design_id, user)
    linked: dict[str, Any] = {}
    if d.template_id:
        t = db.get(GarmentTemplate, d.template_id)
        if t:
            linked["template"] = {"id": str(t.id), "name": t.name, "category": t.category}
    if d.material_id:
        m = db.get(MaterialDefinition, d.material_id)
        if m:
            linked["material"] = {
                "id": str(m.id),
                "name": m.name,
                "family": m.family,
                "weight_class": m.weight_class,
                "drape_character": m.drape_character,
            }
    if d.color_palette_id:
        p = db.get(ColorPalette, d.color_palette_id)
        if p:
            linked["palette"] = {"id": str(p.id), "name": p.name, "colors": p.colors}

    revision_rows = list(
        db.scalars(
            select(DesignRevision)
            .where(DesignRevision.design_id == d.id)
            .order_by(DesignRevision.revision_number.desc())
            .limit(5)
        ).all()
    )
    revision_count = int(
        db.scalar(select(func.count()).select_from(DesignRevision).where(DesignRevision.design_id == d.id)) or 0
    )
    latest_revision_number = revision_rows[0].revision_number if revision_rows else None
    revision_summary = {
        "count": revision_count,
        "latest_revision_number": latest_revision_number,
        "recent": [
            {
                "revision_number": r.revision_number,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in revision_rows
        ],
    }

    return {
        "schema_version": "1.0",
        "export_kind": "fashionrise.handoff.manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": {
            "id": str(d.id),
            "title": d.title,
            "description": d.description,
            "garment_category": d.garment_category,
            "status": d.status,
            "visibility": d.visibility,
            "template_id": str(d.template_id) if d.template_id else None,
            "material_id": str(d.material_id) if d.material_id else None,
            "color_palette_id": str(d.color_palette_id) if d.color_palette_id else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        },
        "linked_catalog": linked,
        "design_data": d.design_data,
        "metadata": d.metadata_,
        "revision_summary": revision_summary,
        "export_hints": {
            "intended_consumers": ["maker", "atelier", "classroom"],
            "next_exports": ["spec_sheet_pdf", "cut_plan_pdf"],
            "notes": "This manifest is JSON-first; print-ready package export types are planned.",
        },
        "measurements_placeholder": {
            "note": "Reserved for bust, waist, hip, inseam, etc. — add when fit capture ships.",
        },
    }


def build_handoff_spec_sheet(db: Session, design_id: uuid.UUID, user: User) -> dict[str, Any]:
    """Owner-only JSON spec sheet view for maker handoff (lightweight print-friendly data model)."""
    base = build_handoff_manifest(db, design_id, user)
    d = base["design"]
    linked = base.get("linked_catalog", {})
    material = linked.get("material")
    palette = linked.get("palette")
    template = linked.get("template")
    design_data = base.get("design_data", {})
    return {
        "schema_version": "1.0",
        "export_kind": "fashionrise.handoff.spec_sheet_v1",
        "generated_at": base.get("generated_at"),
        "design": {
            "id": d.get("id"),
            "title": d.get("title"),
            "garment_category": d.get("garment_category"),
            "status": d.get("status"),
        },
        "style_recipe": {
            "template": template.get("name") if template else None,
            "material": material.get("name") if material else None,
            "palette": palette.get("name") if palette else None,
            "silhouette_volume": design_data.get("silhouette_volume"),
            "drape_expression": design_data.get("drape_expression"),
            "layering_depth": design_data.get("layering_depth"),
            "seam_accent": design_data.get("seam_accent"),
            "notes": {
                "trim": design_data.get("trim_notes"),
                "accent": design_data.get("accent_notes"),
            },
        },
        "measurements_placeholder": base.get("measurements_placeholder"),
        "revision_summary": base.get("revision_summary"),
    }


def build_handoff_spec_sheet_pdf_placeholder(db: Session, design_id: uuid.UUID, user: User) -> dict[str, Any]:
    """Generate placeholder PDF file, register export row, and return handoff export payload."""
    base = build_handoff_spec_sheet(db, design_id, user)
    d = base["design"]
    title = d.get("title") or "Untitled"
    pdf_text = (
        f"%PDF-1.1\n"
        f"% FashionRise placeholder spec sheet\n"
        f"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        f"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n"
        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        f"4 0 obj\n<< /Length 80 >>\nstream\n"
        f"BT /F1 12 Tf 72 740 Td (FashionRise Spec Sheet Placeholder) Tj 0 -18 Td (Title: {title}) Tj ET\n"
        f"endstream\nendobj\nxref\n0 5\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n0\n%%EOF\n"
    ).encode("utf-8")

    storage = LocalStorageBackend()
    key = f"handoff/spec_sheet_{design_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_url = storage.save_file(key=key, data=BytesIO(pdf_text), content_type="application/pdf")
    ex = export_service.create_export(
        db,
        user,
        ExportCreate(
            design_id=design_id,
            export_type="spec_sheet_pdf",
            file_url=file_url,
            metadata={
                "source": "handoff_placeholder",
                "export_kind": "spec_sheet_pdf",
                "design_title": title,
            },
        ),
    )
    return {
        "schema_version": "1.0",
        "export_kind": "fashionrise.handoff.spec_sheet_pdf_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": d,
        "style_recipe": base.get("style_recipe"),
        "revision_summary": base.get("revision_summary"),
        "export": {
            "id": str(ex.id),
            "design_id": str(ex.design_id),
            "export_type": ex.export_type,
            "file_url": ex.file_url,
            "metadata": ex.metadata_,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
        },
    }


def list_design_revisions(
    db: Session, design_id: uuid.UUID, user: User, *, limit: int = 50, offset: int = 0
) -> list[DesignRevision]:
    _owned_design(db, design_id, user)
    return list(
        db.scalars(
            select(DesignRevision)
            .where(DesignRevision.design_id == design_id)
            .order_by(DesignRevision.revision_number.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


def append_design_revision(
    db: Session, design_id: uuid.UUID, user: User, design_data: dict, notes: str | None
) -> DesignRevision:
    _owned_design(db, design_id, user)
    max_num = db.scalar(select(func.max(DesignRevision.revision_number)).where(DesignRevision.design_id == design_id))
    next_n = (max_num or 0) + 1
    rev = DesignRevision(
        design_id=design_id,
        user_id=user.id,
        revision_number=next_n,
        design_data=design_data,
        notes=notes,
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)
    return rev


def get_design_revision(db: Session, design_id: uuid.UUID, user: User, revision_number: int) -> DesignRevision:
    _owned_design(db, design_id, user)
    r = db.scalar(
        select(DesignRevision).where(
            DesignRevision.design_id == design_id,
            DesignRevision.revision_number == revision_number,
        )
    )
    if not r:
        raise NotFoundError("Revision not found")
    return r


def _bump_design_count(db: Session, user_id: uuid.UUID, delta: int) -> None:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile:
        profile.designs_count = max(0, profile.designs_count + delta)
        db.add(profile)
