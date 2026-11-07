"""Web Push subscription API for Runway notifications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.errors import ServiceUnavailableError, ValidationAppError
from app.db.session import get_db
from app.schemas.push import (
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
