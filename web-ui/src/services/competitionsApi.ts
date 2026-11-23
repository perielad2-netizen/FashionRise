import { apiRequest } from '@/services/api/client'

export type CompetitionStanding = {
  group_index: number | null
  group_id: string | null
  participant_count: number
  designer_rank: number | null
  designer_score: number
}

export type CompetitionStatus = {
  week_start: string
  week_end: string
  week_key: string
  status: string
  days_remaining: number
  seconds_remaining: number
  group_count: number
  standing: CompetitionStanding | null
  top_designs: Array<{
    gallery_item_id: string
    user_id: string
    username: string | null
    score: number
  }>
  top_designers: Array<{
    user_id: string
    username: string | null
    score: number
  }>
  award_categories: Array<{ id: string; label: string; stars: number }>
  runway_note: string
  publish_note: string
  weekly_rewards_enabled?: boolean
  weekly_rewards_launch_week_start?: string | null
}

export type StreakStatus = {
  current_streak: number
  last_checkin_date: string | null
  lifetime_checkins: number
  days_until_reward: number
  rewarded_this_checkin: boolean
  stars_awarded: number
  reward_every_days: number
  reward_stars: number
  /** Server-authoritative; when false do not advertise active streak Stars. */
  rewards_enabled?: boolean
  /** Consecutive reward-eligible UTC days (post activation boundary). */
  reward_streak?: number
  /** 1..reward_every_days progress for UI (never exceeds the cycle). */
  cycle_day?: number
}

/** Map unbounded consecutive days onto a 1..N reward-cycle progress. */
export function streakCycleDay(streak: StreakStatus): number {
  const every = Math.max(1, streak.reward_every_days || 7)
  if (typeof streak.cycle_day === 'number' && streak.cycle_day > 0) {
    return Math.min(every, streak.cycle_day)
  }
  const raw = Math.max(0, streak.current_streak || 0)
  if (raw <= 0) return 0
  return ((raw - 1) % every) + 1
}

export type CompetitionAward = {
  category: string
  label: string
  user_id: string
  username: string | null
  gallery_item_id: string | null
  stars_amount: number
  score: number
  group_index: number | null
  week_start: string
  claimed_at?: string | null
}

export type PendingAwardClaim = {
  id: string
  category: string
  label: string
  stars_amount: number
  week_start: string
  week_label: string
}

export type ClaimAwardResult = {
  id: string
  category: string
  label: string
  stars_amount: number
  week_start: string
  claimed_at: string | null
  newly_credited: boolean
  already_claimed: boolean
  ai_stars: number
}

export type CategoryBoardEntry = {
  rank: number
  user_id: string
  username: string | null
  display_name: string | null
  avatar_url: string | null
  score: number
  gallery_item_id: string | null
  look_title: string | null
}

export type CategoryBoard = {
  category: string
  label: string
  stars: number
  week_start: string
  week_end: string
  group_index: number | null
  entries: CategoryBoardEntry[]
  empty_reason: string | null
}

export function fetchCompetitionStatus() {
  return apiRequest<CompetitionStatus>('/competitions/status', { method: 'GET' })
}

export function fetchCategoryBoard(categoryId: string, limit = 20) {
  const q = new URLSearchParams({ limit: String(limit) })
  return apiRequest<CategoryBoard>(
    `/competitions/categories/${encodeURIComponent(categoryId)}/board?${q}`,
    { method: 'GET' },
  )
}

export function fetchCompetitionAwards(params?: { week_start?: string; group_index?: number }) {
  const q = new URLSearchParams()
  if (params?.week_start) q.set('week_start', params.week_start)
  if (params?.group_index != null) q.set('group_index', String(params.group_index))
  const suffix = q.toString() ? `?${q.toString()}` : ''
  return apiRequest<CompetitionAward[]>(`/competitions/awards${suffix}`, { method: 'GET' })
}

export function fetchPendingAwardClaims() {
  return apiRequest<PendingAwardClaim[]>('/competitions/awards/pending', { method: 'GET' })
}

export function claimCompetitionAward(awardId: string) {
  return apiRequest<ClaimAwardResult>(
    `/competitions/awards/${encodeURIComponent(awardId)}/claim`,
    { method: 'POST' },
  )
}

export function fetchStreakStatus() {
  return apiRequest<StreakStatus>('/competitions/streak', { method: 'GET' })
}

export function postStreakCheckIn() {
  return apiRequest<StreakStatus>('/competitions/streak/check-in', { method: 'POST' })
}
