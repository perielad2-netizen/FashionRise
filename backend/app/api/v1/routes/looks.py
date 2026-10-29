"""My Looks — owner-scoped gallery over completed Magic polish jobs."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.look import LookListResponse, LookRead, LookUpdate
from app.services import looks_service

router = APIRouter()


@router.get("", response_model=LookListResponse)
def list_looks(
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
    filter: Literal["all", "favorites", "archived"] = Query("all"),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> LookListResponse:
    return looks_service.list_looks(
        db,
        user,
        filter_name=filter,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{look_id}", response_model=LookRead)
def get_look(
    look_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> LookRead:
    return looks_service.get_look(db, user, look_id)


@router.patch("/{look_id}", response_model=LookRead)
def update_look(
    look_id: uuid.UUID,
    data: LookUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> LookRead:
    return looks_service.update_look(db, user, look_id, data)


@router.delete("/{look_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_look(
    look_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> Response:
    """Remove a look from My Looks (tombstone). Does not erase AI job image files."""
    looks_service.delete_look(db, user, look_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
