import { useEffect, useState } from 'react'
import { Flame } from 'lucide-react'
import { fetchStreakStatus, type StreakStatus } from '@/services/competitionsApi'
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

  return (
    <section className={styles.strip} aria-label="Login streak">
      <div className={styles.summary}>
        <span className={styles.streak}>
          <Flame size={14} aria-hidden />
          Login streak {streak.current_streak}/7
        </span>
      </div>
    </section>
  )
}
