"""Runway Friends API — private circle for the next social slices."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.friendship import FriendRequestCreate, FriendshipRead
from app.services import friendship_service as fs

router = APIRouter()


@router.get("", response_model=list[FriendshipRead])
def list_my_friends(user: CurrentUser, db: Session = Depends(get_db)) -> list[FriendshipRead]:
    return fs.list_friends(db, user)


@router.get("/requests", response_model=list[FriendshipRead])
def list_incoming_friend_requests(
    user: CurrentUser, db: Session = Depends(get_db)
) -> list[FriendshipRead]:
    return fs.list_incoming_requests(db, user)


@router.post("/request", response_model=FriendshipRead, status_code=201)
def request_friend(
    body: FriendRequestCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FriendshipRead:
    return fs.request_friend(db, user, username=body.username, user_id=body.user_id)


@router.post("/{friendship_id}/accept", response_model=FriendshipRead)
def accept_friend_request(
    friendship_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FriendshipRead:
    return fs.accept_friend(db, user, friendship_id)


@router.delete("/{friend_user_id}", status_code=204, response_class=Response)
def remove_friend(
    friend_user_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    fs.remove_friend(db, user, friend_user_id)
    return Response(status_code=204)
