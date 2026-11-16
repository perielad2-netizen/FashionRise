import { useEffect, useMemo, useState } from 'react'
import { Trophy, Flame, Globe2 } from 'lucide-react'
import {
  fetchCompetitionAwards,
  fetchCompetitionStatus,
  fetchStreakStatus,
  type CompetitionAward,
  type CompetitionStatus,
  type StreakStatus,
} from '@/services/competitionsApi'
import styles from './CompetitionStrip.module.css'

function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  if (d > 0) return `${d}d ${h}h left`
  const m = Math.floor((s % 3600) / 60)
  return `${h}h ${m}m left`
}

function localWeekLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      timeZoneName: 'short',
    })
  } catch {
    return iso.slice(0, 10)
  }
}

export function CompetitionStrip() {
  const [status, setStatus] = useState<CompetitionStatus | null>(null)
  const [streak, setStreak] = useState<StreakStatus | null>(null)
  const [awards, setAwards] = useState<CompetitionAward[]>([])
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [comp, streakStatus] = await Promise.all([
          fetchCompetitionStatus(),
          fetchStreakStatus().catch(() => null),
        ])
        if (cancelled) return
        setStatus(comp)
        if (streakStatus) setStreak(streakStatus)
        const weekAwards = await fetchCompetitionAwards().catch(() => [])
        if (!cancelled) setAwards(weekAwards)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Competition unavailable')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const countdown = useMemo(
    () => (status ? formatCountdown(status.seconds_remaining) : ''),
    [status],
  )

  if (error || !status) {
    return null
  }

  return (
    <section className={styles.strip} aria-label="Weekly FashionRise competition">
      <button type="button" className={styles.summary} onClick={() => setOpen((v) => !v)}>
        <span className={styles.badge}>
          <Trophy size={14} aria-hidden />
          Week of {localWeekLabel(status.week_start)}
        </span>
        <span className={styles.meta}>{countdown}</span>
        {status.standing?.group_index != null && (
          <span className={styles.meta}>Group {status.standing.group_index + 1}</span>
        )}
        {streak && (
          <span className={styles.streak}>
            <Flame size={14} aria-hidden />
            {streak.rewards_enabled
              ? `${streak.current_streak}/7 · ${streak.days_until_reward} to +${streak.reward_stars}★`
              : `Login streak ${streak.current_streak}/7`}
          </span>
        )}
      </button>

      {open && (
        <div className={styles.panel}>
          <p className={styles.note}>{status.publish_note}</p>
          <p className={styles.note}>
            <Globe2 size={14} aria-hidden /> {status.runway_note}
          </p>
          {status.standing && (
            <p className={styles.standing}>
              Your weekly designer standing:{' '}
              {status.standing.designer_rank
                ? `#${status.standing.designer_rank} (${status.standing.designer_score} pts)`
                : 'publish or engage to climb'}
            </p>
          )}
          {status.weekly_rewards_enabled ? (
            <div className={styles.cats}>
              {status.award_categories.map((cat) => (
                <span key={cat.id} className={styles.cat}>
                  {cat.label} · {cat.stars}★
                </span>
              ))}
            </div>
          ) : (
            <p className={styles.note}>Weekly Star prizes are not active yet.</p>
          )}
          {status.top_designs.length > 0 && (
            <div className={styles.list}>
              <h3>Group top designs</h3>
              <ol>
                {status.top_designs.slice(0, 5).map((row) => (
                  <li key={row.gallery_item_id}>
                    @{row.username ?? 'designer'} · {row.score} pts
                  </li>
                ))}
              </ol>
            </div>
          )}
          {awards.length > 0 && (
            <div className={styles.list}>
              <h3>Recent winners</h3>
              <ul>
                {awards.slice(0, 6).map((award) => (
                  <li key={`${award.category}-${award.user_id}-${award.week_start}`}>
                    {award.label}: @{award.username ?? 'winner'} · {award.stars_amount}★
                  </li>
                ))}
              </ul>
            </div>
          )}
          {streak?.rewards_enabled && streak.rewarded_this_checkin && streak.stars_awarded > 0 ? (
            <p className={styles.reward}>Streak complete — +{streak.stars_awarded} Stars</p>
          ) : null}
        </div>
      )}
    </section>
  )
}
