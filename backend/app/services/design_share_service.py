"""Share a saved design with an accepted friend so they can continue it.

Creates a recipient-owned saved-design copy, grants read access to the
sender's fabrics and models (croquis), and records the transfer so friends
can pass the design back and forth.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.design_collaboration import (
    ASSET_KIND_CROQUIS,
    ASSET_KIND_FABRIC,
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

    meta: dict[str, Any] = {
        "designKind": SAVED_DESIGN_KIND,
        "envelope": True,
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

    collaboration = _get_or_create_collaboration(
        db, from_user=user, to_user=friend, origin_design_id=source.id
    )
    fabrics_granted, croquis_granted = _grant_sender_library(
        db, collaboration=collaboration, granter=user, grantee=friend
    )

    transfer_id = uuid.uuid4()
    received = _copy_saved_design_for_recipient(
        db,
        source=source,
        from_user=user,
        to_user=friend,
        collaboration=collaboration,
        transfer_id=transfer_id,
        note=data.note,
    )

    transfer = DesignShareTransfer(
        id=transfer_id,
        collaboration_id=collaboration.id,
        from_user_id=user.id,
        to_user_id=friend.id,
        source_design_id=source.id,
        received_design_id=received.id,
        note=(data.note.strip() if data.note and data.note.strip() else None),
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    db.refresh(received)

    received_read = DesignRead.model_validate(received)
    transfer_read = DesignShareTransferRead(
        id=transfer.id,
        collaboration_id=transfer.collaboration_id,
        from_user_id=transfer.from_user_id,
        to_user_id=transfer.to_user_id,
        source_design_id=transfer.source_design_id,
        received_design_id=transfer.received_design_id,
        note=transfer.note,
        created_at=transfer.created_at,
        from_username=user.username,
        to_username=friend.username,
        received_design=received_read,
        fabrics_granted=fabrics_granted,
        croquis_granted=croquis_granted,
    )
    return DesignShareResult(
        transfer=transfer_read,
        received_design=received_read,
        collaboration_id=collaboration.id,
        message=(
            f"Shared with {friend.username}. They can open it in My Designs, "
            "use your fabrics and models, create Magic, and publish to FashionRise."
        ),
    )


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
