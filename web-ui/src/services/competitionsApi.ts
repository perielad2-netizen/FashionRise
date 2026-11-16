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
}

export function fetchCompetitionStatus() {
  return apiRequest<CompetitionStatus>('/competitions/status', { method: 'GET' })
}

export function fetchCompetitionAwards(params?: { week_start?: string; group_index?: number }) {
  const q = new URLSearchParams()
  if (params?.week_start) q.set('week_start', params.week_start)
  if (params?.group_index != null) q.set('group_index', String(params.group_index))
  const suffix = q.toString() ? `?${q.toString()}` : ''
  return apiRequest<CompetitionAward[]>(`/competitions/awards${suffix}`, { method: 'GET' })
}

export function fetchStreakStatus() {
  return apiRequest<StreakStatus>('/competitions/streak', { method: 'GET' })
}

export function postStreakCheckIn() {
  return apiRequest<StreakStatus>('/competitions/streak/check-in', { method: 'POST' })
}
