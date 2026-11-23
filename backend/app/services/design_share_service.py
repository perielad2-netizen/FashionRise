"""Share a saved design with an accepted friend so they can continue it.

Share creates a *pending* invite. Only when the friend accepts do we create
their saved-design copy and grant fabrics/models. Friends can pass designs
back and forth; each send needs approval again.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.design_collaboration import (
    ASSET_KIND_CROQUIS,
    ASSET_KIND_FABRIC,
    SHARE_STATUS_ACCEPTED,
    SHARE_STATUS_PENDING,
    SHARE_STATUS_REJECTED,
    DesignCollaboration,
    DesignShareTransfer,
    SharedAssetGrant,
)
from app.models.fabric_asset import FabricAsset
from app.models.garment_design import GarmentDesign
from app.models.personal_croquis import PersonalCroquis
from app.models.private_media_asset import PrivateMediaAsset
from app.models.user import User
from app.schemas.design import DesignCreate, DesignRead
from app.schemas.design_share import DesignShareRequest, DesignShareResult, DesignShareTransferRead
from app.services import design_service, friendship_service

SAVED_DESIGN_KIND = design_service.SAVED_DESIGN_KIND
SAVED_DESIGN_V2 = design_service.SAVED_DESIGN_V2


def _pair_ids(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a.hex < b.hex else (b, a)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_collaboration(
    db: Session,
    *,
    from_user: User,
    to_user: User,
    origin_design_id: uuid.UUID,
) -> DesignCollaboration:
    low, high = _pair_ids(from_user.id, to_user.id)
    row = db.scalar(
        select(DesignCollaboration).where(
            DesignCollaboration.user_low_id == low,
            DesignCollaboration.user_high_id == high,
        )
    )
    if row is not None:
        row.updated_at = _utcnow()
        db.add(row)
        return row
    row = DesignCollaboration(
        id=uuid.uuid4(),
        user_low_id=low,
        user_high_id=high,
        created_by_id=from_user.id,
        origin_design_id=origin_design_id,
    )
    db.add(row)
    db.flush()
    return row


def _grant_asset(
    db: Session,
    *,
    collaboration_id: uuid.UUID,
    granter_id: uuid.UUID,
    grantee_id: uuid.UUID,
    asset_kind: str,
    asset_id: uuid.UUID,
) -> bool:
    # Sessions use autoflush=False — flush so library + pinned grants in the same
    # accept do not insert duplicate rows for uq_shared_asset_grants_target.
    db.flush()
    existing = db.scalar(
        select(SharedAssetGrant).where(
            SharedAssetGrant.collaboration_id == collaboration_id,
            SharedAssetGrant.grantee_id == grantee_id,
            SharedAssetGrant.asset_kind == asset_kind,
            SharedAssetGrant.asset_id == asset_id,
        )
    )
    if existing is not None:
        return False
    db.add(
        SharedAssetGrant(
            id=uuid.uuid4(),
            collaboration_id=collaboration_id,
            granter_id=granter_id,
            grantee_id=grantee_id,
            asset_kind=asset_kind,
            asset_id=asset_id,
        )
    )
    return True


def _snapshot_personal_croquis_id(design_data: dict[str, Any] | None) -> uuid.UUID | None:
    """Extract the Studio personal model pin from a saved-design envelope/snapshot."""
    if not isinstance(design_data, dict):
        return None
    snap = design_data.get("snapshot")
    source = snap if isinstance(snap, dict) else design_data
    if not isinstance(source, dict):
        return None
    raw = source.get("personalCroquisId") or source.get("personal_croquis_id")
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _grant_sender_library(
    db: Session,
    *,
    collaboration: DesignCollaboration,
    granter: User,
    grantee: User,
) -> tuple[int, int]:
    """Grant the recipient read access to all of the sender's fabrics and models."""
    fabrics = (
        db.query(FabricAsset)
        .filter(FabricAsset.owner_id == granter.id, FabricAsset.deleted_at.is_(None))
        .all()
    )
    croquis_rows = (
        db.query(PersonalCroquis)
        .filter(
            PersonalCroquis.owner_id == granter.id,
            PersonalCroquis.archived_at.is_(None),
            PersonalCroquis.deleted_at.is_(None),
            PersonalCroquis.erase_requested_at.is_(None),
        )
        .all()
    )
    fabric_n = 0
    croquis_n = 0
    for fabric in fabrics:
        if _grant_asset(
            db,
            collaboration_id=collaboration.id,
            granter_id=granter.id,
            grantee_id=grantee.id,
            asset_kind=ASSET_KIND_FABRIC,
            asset_id=fabric.id,
        ):
            fabric_n += 1
    for croquis in croquis_rows:
        if _grant_asset(
            db,
            collaboration_id=collaboration.id,
            granter_id=granter.id,
            grantee_id=grantee.id,
            asset_kind=ASSET_KIND_CROQUIS,
            asset_id=croquis.id,
        ):
            croquis_n += 1
    return fabric_n, croquis_n


def _grant_pinned_croquis_from_design(
    db: Session,
    *,
    collaboration: DesignCollaboration,
    granter: User,
    grantee: User,
    design_data: dict[str, Any] | None,
) -> bool:
    """Always grant the design's pinned My Model, even when it is archived.

    Historical Studio pins survive archive; recipients still need underlay access.
    Erased/deleted croquis are not granted.
    """
    pin_id = _snapshot_personal_croquis_id(design_data)
    if pin_id is None:
        return False
    croquis = (
        db.query(PersonalCroquis)
        .filter(
            PersonalCroquis.id == pin_id,
            PersonalCroquis.owner_id == granter.id,
            PersonalCroquis.deleted_at.is_(None),
            PersonalCroquis.erase_requested_at.is_(None),
        )
        .first()
    )
    if croquis is None:
        return False
    return _grant_asset(
        db,
        collaboration_id=collaboration.id,
        granter_id=granter.id,
        grantee_id=grantee.id,
        asset_kind=ASSET_KIND_CROQUIS,
        asset_id=croquis.id,
    )


def ensure_croquis_grant_for_shared_pin(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    croquis: PersonalCroquis | None = None,
) -> bool:
    """Repair missing grants when a received shared design still pins this model.

    Older accepts sometimes granted the live library but missed the pinned id
    (or the pin belonged to a friend who was not the library pass at accept).
    """
    row = croquis or db.get(PersonalCroquis, croquis_id)
    if row is None:
        return False
    if row.owner_id == user.id:
        return False
    if row.deleted_at is not None or row.erase_requested_at is not None:
        return False
    if has_croquis_grant(db, user, croquis_id):
        return False

    # Look for a received shared design owned by this user that still pins it.
    candidates = (
        db.query(GarmentDesign)
        .filter(GarmentDesign.user_id == user.id)
        .order_by(GarmentDesign.updated_at.desc())
        .limit(200)
        .all()
    )
    matched: GarmentDesign | None = None
    for design in candidates:
        meta = design.metadata_ or {}
        if not meta.get("receivedViaShare"):
            continue
        pin = _snapshot_personal_croquis_id(design.design_data if isinstance(design.design_data, dict) else None)
        if pin == croquis_id:
            matched = design
            break
    if matched is None:
        return False

    granter = db.get(User, row.owner_id)
    if granter is None or not granter.is_active:
        return False
    try:
        friendship_service.require_accepted_friends(db, user, granter)
    except (ForbiddenError, NotFoundError, ConflictError, ValidationAppError):
        return False

    origin_id = matched.id
    raw_origin = (matched.metadata_ or {}).get("sharedFromDesignId")
    if raw_origin:
        try:
            origin_id = uuid.UUID(str(raw_origin))
        except (TypeError, ValueError):
            origin_id = matched.id
    collaboration = _get_or_create_collaboration(
        db, from_user=granter, to_user=user, origin_design_id=origin_id
    )
    created = _grant_asset(
        db,
        collaboration_id=collaboration.id,
        granter_id=granter.id,
        grantee_id=user.id,
        asset_kind=ASSET_KIND_CROQUIS,
        asset_id=croquis_id,
    )
    if created:
        db.flush()
    return created


def _copy_saved_design_for_recipient(
    db: Session,
    *,
    source: GarmentDesign,
    from_user: User,
    to_user: User,
    collaboration: DesignCollaboration,
    transfer_id: uuid.UUID,
    note: str | None,
) -> GarmentDesign:
    design_data = copy.deepcopy(source.design_data or {})
    schema = design_data.get("schema")
    if schema not in design_service.SAVED_DESIGN_SCHEMAS:
        # Wrap a rare non-envelope snapshot as v2 so create_design accepts it.
        design_data = {
            "schema": SAVED_DESIGN_V2,
            "saveRequestId": str(uuid.uuid4()),
            "savedAt": _utcnow().isoformat(),
            "sourceRevision": 0,
            "snapshot": design_data if isinstance(design_data, dict) else {},
        }
    else:
        design_data["saveRequestId"] = str(uuid.uuid4())
        design_data["savedAt"] = _utcnow().isoformat()

    base_title = (source.title or "Untitled design").strip() or "Untitled design"
    title = f"From {from_user.username}: {base_title}"
    if len(title) > 300:
        title = title[:297] + "…"

    schema_name = design_data.get("schema")
    if schema_name not in design_service.SAVED_DESIGN_SCHEMAS:
        schema_name = SAVED_DESIGN_V2
    meta: dict[str, Any] = {
        "designKind": SAVED_DESIGN_KIND,
        # Must be a schema string — boolean True blocks DELETE /designs/saved/{id}.
        "envelope": schema_name,
        "saveRequestId": design_data.get("saveRequestId"),
        "savedAt": design_data.get("savedAt"),
        "receivedViaShare": True,
        "collaborationId": str(collaboration.id),
        "sharedFromUserId": str(from_user.id),
        "sharedFromUsername": from_user.username,
        "sharedFromDesignId": str(source.id),
        "shareTransferId": str(transfer_id),
    }
    if note:
        meta["shareNote"] = note

    created = design_service.create_design(
        db,
        to_user,
        DesignCreate(
            title=title,
            description=source.description,
            garment_category=source.garment_category or "custom",
            template_id=source.template_id,
            material_id=source.material_id,
            color_palette_id=source.color_palette_id,
            design_data=design_data,
            metadata=meta,
            visibility="private",
            status="draft",
        ),
    )
    return created


def _transfer_read(
    db: Session,
    transfer: DesignShareTransfer,
    *,
    fabrics_granted: int = 0,
    croquis_granted: int = 0,
    received: GarmentDesign | None = None,
) -> DesignShareTransferRead:
    from_user = db.get(User, transfer.from_user_id)
    to_user = db.get(User, transfer.to_user_id)
    received_read = DesignRead.model_validate(received) if received is not None else None
    if received_read is None and transfer.received_design_id is not None:
        row = db.get(GarmentDesign, transfer.received_design_id)
        if row is not None:
            received_read = DesignRead.model_validate(row)
    return DesignShareTransferRead(
        id=transfer.id,
        collaboration_id=transfer.collaboration_id,
        from_user_id=transfer.from_user_id,
        to_user_id=transfer.to_user_id,
        source_design_id=transfer.source_design_id,
        received_design_id=transfer.received_design_id,
        note=transfer.note,
        status=transfer.status,
        source_title=transfer.source_title,
        responded_at=transfer.responded_at,
        created_at=transfer.created_at,
        from_username=from_user.username if from_user else None,
        to_username=to_user.username if to_user else None,
        received_design=received_read,
        fabrics_granted=fabrics_granted,
        croquis_granted=croquis_granted,
    )


def share_design_with_friend(
    db: Session,
    user: User,
    design_id: uuid.UUID,
    data: DesignShareRequest,
) -> DesignShareResult:
    source = db.get(GarmentDesign, design_id)
    if source is None or source.user_id != user.id:
        # Privacy-preserving: do not reveal foreign design ids.
        raise NotFoundError("Design not found")
    if design_service._is_studio_working_draft(source):  # noqa: SLF001 — intentional reuse
        raise ValidationAppError("Save the design first, then share it with a friend.")
    if not design_service._is_saved_design_row(source):  # noqa: SLF001
        raise ValidationAppError("Only saved designs can be shared with a friend.")

    friend = db.get(User, data.friend_user_id)
    if friend is None or not friend.is_active:
        raise NotFoundError("Friend not found")
    friendship_service.require_accepted_friends(db, user, friend)

    # One open invite per source design + recipient.
    existing_pending = db.scalar(
        select(DesignShareTransfer).where(
            DesignShareTransfer.source_design_id == source.id,
            DesignShareTransfer.to_user_id == friend.id,
            DesignShareTransfer.status == SHARE_STATUS_PENDING,
        )
    )
    if existing_pending is not None:
        raise ConflictError(
            f"You already sent this design to {friend.username}. "
            "Wait for them to accept or decline."
        )

    collaboration = _get_or_create_collaboration(
        db, from_user=user, to_user=friend, origin_design_id=source.id
    )
    transfer = DesignShareTransfer(
        id=uuid.uuid4(),
        collaboration_id=collaboration.id,
        from_user_id=user.id,
        to_user_id=friend.id,
        source_design_id=source.id,
        received_design_id=None,
        note=(data.note.strip() if data.note and data.note.strip() else None),
        status=SHARE_STATUS_PENDING,
        source_title=(source.title or "Untitled design")[:300],
        responded_at=None,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    transfer_read = _transfer_read(db, transfer)
    return DesignShareResult(
        transfer=transfer_read,
        received_design=None,
        collaboration_id=collaboration.id,
        message=(
            f"Invite sent to {friend.username}. "
            "They’ll see it in My Designs and must Accept before it is added."
        ),
    )


def list_incoming_shares(db: Session, user: User) -> list[DesignShareTransferRead]:
    rows = db.scalars(
        select(DesignShareTransfer)
        .where(
            DesignShareTransfer.to_user_id == user.id,
            DesignShareTransfer.status == SHARE_STATUS_PENDING,
        )
        .order_by(DesignShareTransfer.created_at.desc())
    ).all()
    return [_transfer_read(db, row) for row in rows]


def _get_pending_for_recipient(
    db: Session, user: User, transfer_id: uuid.UUID
) -> DesignShareTransfer:
    transfer = db.get(DesignShareTransfer, transfer_id)
    if transfer is None or transfer.to_user_id != user.id:
        raise NotFoundError("Share invite not found")
    if transfer.status != SHARE_STATUS_PENDING:
        raise ConflictError("This share invite was already answered.")
    return transfer


def accept_design_share(db: Session, user: User, transfer_id: uuid.UUID) -> DesignShareResult:
    transfer = _get_pending_for_recipient(db, user, transfer_id)
    if transfer.source_design_id is None:
        raise ValidationAppError("This share invite no longer has a source design.")
    source = db.get(GarmentDesign, transfer.source_design_id)
    if source is None:
        raise NotFoundError("The shared design is no longer available.")
    from_user = db.get(User, transfer.from_user_id)
    if from_user is None or not from_user.is_active:
        raise NotFoundError("The sender is no longer available.")
    friendship_service.require_accepted_friends(db, user, from_user)

    collaboration = db.get(DesignCollaboration, transfer.collaboration_id)
    if collaboration is None:
        collaboration = _get_or_create_collaboration(
            db, from_user=from_user, to_user=user, origin_design_id=source.id
        )
        transfer.collaboration_id = collaboration.id

    fabrics_granted, croquis_granted = _grant_sender_library(
        db, collaboration=collaboration, granter=from_user, grantee=user
    )
    if _grant_pinned_croquis_from_design(
        db,
        collaboration=collaboration,
        granter=from_user,
        grantee=user,
        design_data=source.design_data if isinstance(source.design_data, dict) else None,
    ):
        croquis_granted += 1
    received = _copy_saved_design_for_recipient(
        db,
        source=source,
        from_user=from_user,
        to_user=user,
        collaboration=collaboration,
        transfer_id=transfer.id,
        note=transfer.note,
    )
    transfer.received_design_id = received.id
    transfer.status = SHARE_STATUS_ACCEPTED
    transfer.responded_at = _utcnow()
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    db.refresh(received)

    transfer_read = _transfer_read(
        db,
        transfer,
        fabrics_granted=fabrics_granted,
        croquis_granted=croquis_granted,
        received=received,
    )
    return DesignShareResult(
        transfer=transfer_read,
        received_design=DesignRead.model_validate(received),
        collaboration_id=transfer.collaboration_id,
        message=(
            f"Accepted design from {from_user.username}. "
            "It’s in My Designs — open it to continue, Magic, or publish."
        ),
    )


def reject_design_share(db: Session, user: User, transfer_id: uuid.UUID) -> DesignShareTransferRead:
    transfer = _get_pending_for_recipient(db, user, transfer_id)
    transfer.status = SHARE_STATUS_REJECTED
    transfer.responded_at = _utcnow()
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return _transfer_read(db, transfer)


def has_fabric_grant(db: Session, user: User, asset_id: uuid.UUID) -> bool:
    row = db.scalar(
        select(SharedAssetGrant.id).where(
            SharedAssetGrant.grantee_id == user.id,
            SharedAssetGrant.asset_kind == ASSET_KIND_FABRIC,
            SharedAssetGrant.asset_id == asset_id,
        )
    )
    return row is not None


def has_croquis_grant(db: Session, user: User, croquis_id: uuid.UUID) -> bool:
    row = db.scalar(
        select(SharedAssetGrant.id).where(
            SharedAssetGrant.grantee_id == user.id,
            SharedAssetGrant.asset_kind == ASSET_KIND_CROQUIS,
            SharedAssetGrant.asset_id == croquis_id,
        )
    )
    return row is not None


def list_granted_fabric_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(SharedAssetGrant.asset_id).where(
                SharedAssetGrant.grantee_id == user.id,
                SharedAssetGrant.asset_kind == ASSET_KIND_FABRIC,
            )
        ).all()
    )


def list_granted_croquis_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(SharedAssetGrant.asset_id).where(
                SharedAssetGrant.grantee_id == user.id,
                SharedAssetGrant.asset_kind == ASSET_KIND_CROQUIS,
            )
        ).all()
    )


def list_accessible_fabrics(db: Session, user: User) -> list[FabricAsset]:
    """Owner fabrics plus fabrics granted via design collaborations."""
    from app.services import fabric_asset_service

    owned = fabric_asset_service.list_owned_fabric_assets(db, user)
    granted_ids = list_granted_fabric_ids(db, user)
    if not granted_ids:
        return owned
    granted = (
        db.query(FabricAsset)
        .filter(FabricAsset.id.in_(granted_ids), FabricAsset.deleted_at.is_(None))
        .order_by(FabricAsset.created_at.desc())
        .all()
    )
    seen = {row.id for row in owned}
    merged = list(owned)
    for row in granted:
        if row.id not in seen:
            merged.append(row)
            seen.add(row.id)
    return merged


def get_accessible_fabric_asset(
    db: Session,
    user: User,
    asset_id: uuid.UUID,
    *,
    include_deleted: bool = True,
) -> FabricAsset:
    from fastapi import HTTPException, status

    q = db.query(FabricAsset).filter(FabricAsset.id == asset_id)
    if not include_deleted:
        q = q.filter(FabricAsset.deleted_at.is_(None))
    row = q.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric not found")
    if row.owner_id == user.id or has_fabric_grant(db, user, asset_id):
        return row
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric not found")


def list_accessible_croquis(db: Session, user: User) -> list[PersonalCroquis]:
    from app.services import personal_croquis_service as pcs

    owned = pcs.list_owned_personal_croquis(db, user)
    granted_ids = list_granted_croquis_ids(db, user)
    if not granted_ids:
        return owned
    granted = (
        db.query(PersonalCroquis)
        .filter(
            PersonalCroquis.id.in_(granted_ids),
            PersonalCroquis.archived_at.is_(None),
            PersonalCroquis.deleted_at.is_(None),
            PersonalCroquis.erase_requested_at.is_(None),
        )
        .order_by(PersonalCroquis.created_at.desc())
        .all()
    )
    seen = {row.id for row in owned}
    merged = list(owned)
    for row in granted:
        if row.id not in seen:
            merged.append(row)
            seen.add(row.id)
    return merged


def get_accessible_croquis(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> PersonalCroquis:
    from fastapi import HTTPException, status

    q = db.query(PersonalCroquis).filter(
        PersonalCroquis.id == croquis_id,
        PersonalCroquis.deleted_at.is_(None),
        PersonalCroquis.erase_requested_at.is_(None),
    )
    if not include_archived:
        q = q.filter(PersonalCroquis.archived_at.is_(None))
    row = q.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")
    if row.owner_id == user.id or has_croquis_grant(db, user, croquis_id):
        return row
    # Repair older shared designs that still pin this model without a grant row.
    if ensure_croquis_grant_for_shared_pin(db, user, croquis_id, croquis=row):
        return row
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")


def media_asset_accessible_via_croquis_grant(
    db: Session, user: User, asset: PrivateMediaAsset
) -> bool:
    """True when the private media belongs to a croquis granted to the user."""
    if asset.owner_id == user.id:
        return True
    # Match croquis that reference this asset as source or version output.
    croquis_ids = list_granted_croquis_ids(db, user)
    if not croquis_ids:
        return False
    # Source photo asset on croquis
    hit = db.scalar(
        select(PersonalCroquis.id).where(
            PersonalCroquis.id.in_(croquis_ids),
            PersonalCroquis.source_asset_id == asset.id,
        )
    )
    if hit is not None:
        return True
    # Generated version still asset
    from app.models.personal_croquis import PersonalCroquisVersion

    hit_v = db.scalar(
        select(PersonalCroquisVersion.id).where(
            PersonalCroquisVersion.croquis_id.in_(croquis_ids),
            PersonalCroquisVersion.generated_asset_id == asset.id,
        )
    )
    return hit_v is not None
