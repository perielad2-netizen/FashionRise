"""Web Push + native device registration for Runway notifications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.errors import ServiceUnavailableError, ValidationAppError
from app.db.session import get_db
from app.schemas.push import (
    NativePushCapability,
    NativePushDeviceCreate,
    NativePushDeviceDelete,
    NativePushDeviceRead,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionRead,
    PushVapidPublicKey,
)
from app.services import push_service as ps

router = APIRouter()


@router.get("/vapid-public-key", response_model=PushVapidPublicKey)
def get_vapid_public_key() -> PushVapidPublicKey:
    key = ps.vapid_public_key()
    return PushVapidPublicKey(public_key=key or "", enabled=ps.push_enabled())


@router.get("/native/capability", response_model=NativePushCapability)
def get_native_push_capability() -> NativePushCapability:
    """Public capability probe — clients must not register when both false."""
    return NativePushCapability(
        android_enabled=ps.native_android_enabled(),
        ios_enabled=ps.native_ios_enabled(),
    )


@router.post("/subscriptions", response_model=PushSubscriptionRead, status_code=201)
def subscribe_push(
    body: PushSubscriptionCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PushSubscriptionRead:
    if not ps.push_enabled():
        raise ServiceUnavailableError("Push notifications are not configured yet")
    ua = request.headers.get("user-agent")
    row = ps.upsert_subscription(db, user, body, user_agent=ua)
    return PushSubscriptionRead.model_validate(row)


@router.delete("/subscriptions", status_code=204, response_class=Response)
def unsubscribe_push(
    body: PushSubscriptionDelete,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    if not str(body.endpoint).strip():
        raise ValidationAppError("endpoint is required")
    ps.delete_subscription(db, user, str(body.endpoint))
    return Response(status_code=204)


@router.get("/subscriptions", response_model=list[PushSubscriptionRead])
def list_my_subscriptions(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[PushSubscriptionRead]:
    rows = ps.list_user_subscriptions(db, user.id)
    return [PushSubscriptionRead.model_validate(r) for r in rows]


@router.post("/native/devices", response_model=NativePushDeviceRead, status_code=201)
def register_native_device(
    body: NativePushDeviceCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> NativePushDeviceRead:
    if body.platform == "android" and not ps.native_android_enabled():
        raise ServiceUnavailableError("Android native push is not enabled")
    if body.platform == "ios" and not ps.native_ios_enabled():
        raise ServiceUnavailableError("iOS native push is not enabled")
    row = ps.upsert_native_device(db, user, body)
    return NativePushDeviceRead.model_validate(row)


@router.delete("/native/devices", status_code=204, response_class=Response)
def unregister_native_device(
    body: NativePushDeviceDelete,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    if not str(body.device_token).strip():
        raise ValidationAppError("device_token is required")
    ps.delete_native_device(db, user, str(body.device_token))
    return Response(status_code=204)


@router.get("/native/devices", response_model=list[NativePushDeviceRead])
def list_my_native_devices(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[NativePushDeviceRead]:
    rows = ps.list_user_native_devices(db, user.id)
    return [NativePushDeviceRead.model_validate(r) for r in rows]
