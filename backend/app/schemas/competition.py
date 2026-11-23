from __future__ import annotations

from pydantic import BaseModel, Field


class AwardCategoryRead(BaseModel):
    id: str
    label: str
    stars: int


class CompetitionStanding(BaseModel):
    group_index: int | None = None
    group_id: str | None = None
    participant_count: int = 0
    designer_rank: int | None = None
    designer_score: int = 0


class ScoredDesignRead(BaseModel):
    gallery_item_id: str
    user_id: str
    username: str | None = None
    score: int


class ScoredDesignerRead(BaseModel):
    user_id: str
    username: str | None = None
    score: int


class CompetitionStatusRead(BaseModel):
    week_start: str
    week_end: str
    week_key: str
    status: str
    days_remaining: float
    seconds_remaining: int
    group_count: int
    standing: CompetitionStanding | None = None
    top_designs: list[ScoredDesignRead] = Field(default_factory=list)
    top_designers: list[ScoredDesignerRead] = Field(default_factory=list)
    award_categories: list[AwardCategoryRead] = Field(default_factory=list)
    runway_note: str
    publish_note: str
    weekly_rewards_enabled: bool = False
    weekly_rewards_launch_week_start: str | None = None


class CompetitionAwardRead(BaseModel):
    category: str
    label: str
    user_id: str
    username: str | None = None
    gallery_item_id: str | None = None
    stars_amount: int
    score: int
    group_index: int | None = None
    week_start: str
    claimed_at: str | None = None


class PendingAwardClaimRead(BaseModel):
    id: str
    category: str
    label: str
    stars_amount: int
    week_start: str
    week_label: str


class ClaimAwardResultRead(BaseModel):
    id: str
    category: str
    label: str
    stars_amount: int
    week_start: str
    claimed_at: str | None = None
    newly_credited: bool = False
    already_claimed: bool = False
    ai_stars: int = 0


class CategoryBoardEntryRead(BaseModel):
    rank: int
    user_id: str
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    score: int
    gallery_item_id: str | None = None
    look_title: str | None = None


class CategoryBoardRead(BaseModel):
    category: str
    label: str
    stars: int
    week_start: str
    week_end: str
    group_index: int | None = None
    entries: list[CategoryBoardEntryRead] = Field(default_factory=list)
    empty_reason: str | None = None


class StreakStatusRead(BaseModel):
    current_streak: int
    last_checkin_date: str | None = None
    lifetime_checkins: int
    days_until_reward: int
    rewarded_this_checkin: bool = False
    stars_awarded: int = 0
    reward_every_days: int = 7
    reward_stars: int = 10
    rewards_enabled: bool = False
    reward_streak: int = 0
    # 1..reward_every_days for UI (never exceeds the cycle, e.g. never 8/7).
    cycle_day: int = 0
