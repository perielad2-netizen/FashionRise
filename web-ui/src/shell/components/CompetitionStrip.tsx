import { useEffect, useState } from 'react'
import { Flame } from 'lucide-react'
import {
  fetchStreakStatus,
  streakCycleDay,
  type StreakStatus,
} from '@/services/competitionsApi'
import styles from './CompetitionStrip.module.css'

export function CompetitionStrip(_props: { defaultOpen?: boolean } = {}) {
  const [streak, setStreak] = useState<StreakStatus | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const streakStatus = await fetchStreakStatus()
        if (!cancelled) setStreak(streakStatus)
      } catch {
        if (!cancelled) setStreak(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (!streak) {
    return null
  }

  const every = Math.max(1, streak.reward_every_days || 7)
  const day = streakCycleDay(streak)

  return (
    <section className={styles.strip} aria-label="Login streak">
      <div className={styles.summary}>
        <span className={styles.streak}>
          <Flame size={14} aria-hidden />
          Login streak {day}/{every}
        </span>
      </div>
    </section>
  )
}
