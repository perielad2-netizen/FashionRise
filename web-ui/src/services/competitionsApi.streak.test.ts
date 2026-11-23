import { describe, expect, it } from 'vitest'
import { streakCycleDay, type StreakStatus } from './competitionsApi'

function streak(partial: Partial<StreakStatus>): StreakStatus {
  return {
    current_streak: 0,
    last_checkin_date: null,
    lifetime_checkins: 0,
    days_until_reward: 7,
    rewarded_this_checkin: false,
    stars_awarded: 0,
    reward_every_days: 7,
    reward_stars: 10,
    ...partial,
  }
}

describe('streakCycleDay', () => {
  it('never renders past the cycle (no 8/7)', () => {
    expect(streakCycleDay(streak({ current_streak: 8 }))).toBe(1)
    expect(streakCycleDay(streak({ current_streak: 7 }))).toBe(7)
    expect(streakCycleDay(streak({ current_streak: 14 }))).toBe(7)
    expect(streakCycleDay(streak({ current_streak: 15 }))).toBe(1)
  })

  it('prefers server cycle_day when present', () => {
    expect(streakCycleDay(streak({ current_streak: 99, cycle_day: 3 }))).toBe(3)
  })
})
