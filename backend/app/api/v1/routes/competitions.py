"""FashionRise weekly competitions + daily login streak."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.competition import (
    CategoryBoardRead,
    CompetitionAwardRead,
    CompetitionStatusRead,
    StreakStatusRead,
)
from app.services import competition_service, login_streak
from app.services.competition_clock import competition_week_start, ensure_utc
from app.services.login_streak import STREAK_REWARD_DAYS, STREAK_REWARD_STARS

router = APIRouter()


@router.get("/status", response_model=CompetitionStatusRead)
def competition_status(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> CompetitionStatusRead:
    raw = competition_service.build_competition_status(db, user)
    return CompetitionStatusRead.model_validate(raw)


@router.get("/categories/{category_id}/board", response_model=CategoryBoardRead)
def competition_category_board(
    category_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> CategoryBoardRead:
    """Live weekly profile/design leaderboard for one award category."""
    raw = competition_service.build_category_board(
        db, user, category=category_id, limit=limit
    )
    return CategoryBoardRead.model_validate(raw)


@router.get("/awards", response_model=list[CompetitionAwardRead])
def competition_awards(
    week_start: datetime | None = Query(default=None),
    group_index: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CompetitionAwardRead]:
    start = ensure_utc(week_start) if week_start is not None else None
    if start is not None:
        start = competition_week_start(start)
    rows = competition_service.list_week_awards(
        db, week_start=start, group_index=group_index
    )
    return [CompetitionAwardRead.model_validate(row) for row in rows]


@router.get("/streak", response_model=StreakStatusRead)
def get_streak(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreakStatusRead:
    status = login_streak.streak_status(db, user)
    return StreakStatusRead(
        current_streak=status.current_streak,
        last_checkin_date=status.last_checkin_date.isoformat() if status.last_checkin_date else None,
        lifetime_checkins=status.lifetime_checkins,
        days_until_reward=status.days_until_reward,
        rewarded_this_checkin=False,
        stars_awarded=0,
        reward_every_days=STREAK_REWARD_DAYS,
        reward_stars=STREAK_REWARD_STARS,
        rewards_enabled=status.rewards_enabled,
        reward_streak=status.reward_streak,
        cycle_day=status.cycle_day,
    )


@router.post("/streak/check-in", response_model=StreakStatusRead)
def post_streak_checkin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreakStatusRead:
    """Foreground authenticated app visit for the UTC calendar day."""
    status = login_streak.record_daily_checkin(db, user)
    return StreakStatusRead(
        current_streak=status.current_streak,
        last_checkin_date=status.last_checkin_date.isoformat() if status.last_checkin_date else None,
        lifetime_checkins=status.lifetime_checkins,
        days_until_reward=status.days_until_reward,
        rewarded_this_checkin=status.rewarded_this_checkin,
        stars_awarded=status.stars_awarded,
        reward_every_days=STREAK_REWARD_DAYS,
        reward_stars=STREAK_REWARD_STARS,
        rewards_enabled=status.rewards_enabled,
        reward_streak=status.reward_streak,
        cycle_day=status.cycle_day,
    )
