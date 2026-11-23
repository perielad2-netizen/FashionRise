"""FashionRise weekly competitions + daily login streak."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.user import User
from uuid import UUID

from app.schemas.competition import (
    CategoryBoardRead,
    ClaimAwardResultRead,
    CompetitionAwardRead,
    CompetitionStatusRead,
    PendingAwardClaimRead,
    StreakStatusRead,
)
from app.services import competition_awards, competition_service, login_streak
from app.services.competition_awards import CATEGORY_LABELS
from app.services.competition_clock import competition_week_start, ensure_utc, week_key
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
def list_competition_awards(
    week_start: datetime | None = Query(default=None),
    group_index: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CompetitionAwardRead]:
    # Named list_* so it does not shadow `from app.services import competition_awards`.
    start = ensure_utc(week_start) if week_start is not None else None
    if start is not None:
        start = competition_week_start(start)
    rows = competition_service.list_week_awards(
        db, week_start=start, group_index=group_index
    )
    return [CompetitionAwardRead.model_validate(row) for row in rows]


@router.get("/awards/pending", response_model=list[PendingAwardClaimRead])
def pending_award_claims(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PendingAwardClaimRead]:
    """One-time claim dialog: locked-week awards the user has not received yet."""
    rows = competition_awards.list_unclaimed_awards_for_user(db, user)
    out: list[PendingAwardClaimRead] = []
    for row in rows:
        wk = week_key(row.week_start)
        out.append(
            PendingAwardClaimRead(
                id=str(row.id),
                category=row.category,
                label=CATEGORY_LABELS.get(row.category, row.category),
                stars_amount=int(row.stars_amount),
                week_start=row.week_start.isoformat(),
                week_label=f"Week of {wk}",
            )
        )
    return out


@router.post("/awards/{award_id}/claim", response_model=ClaimAwardResultRead)
def claim_award(
    award_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClaimAwardResultRead:
    """Confirm Receive Stars for a weekly award (idempotent)."""
    result = competition_awards.claim_competition_award(db, user, award_id)
    return ClaimAwardResultRead.model_validate(result)


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
