import { useCallback, useEffect, useState } from 'react'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { useAuth } from '@/services/auth/AuthProvider'
import {
  claimCompetitionAward,
  fetchPendingAwardClaims,
  type PendingAwardClaim,
} from '@/services/competitionsApi'

/**
 * One-time winner dialog after a competition week locks.
 * Stars are credited only when the winner taps Receive Stars.
 */
export function WeeklyAwardClaimDialog() {
  const { user, refreshUser } = useAuth()
  const [queue, setQueue] = useState<PendingAwardClaim[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshPending = useCallback(async () => {
    if (!user?.id) {
      setQueue([])
      return
    }
    try {
      const pending = await fetchPendingAwardClaims()
      setQueue(pending)
      setError(null)
    } catch {
      // Best-effort — do not block Studio if the awards endpoint is down.
    }
  }, [user?.id])

  useEffect(() => {
    void refreshPending()
  }, [refreshPending])

  const current = queue[0] ?? null

  const onReceive = useCallback(async () => {
    if (!current || busy) return
    setBusy(true)
    setError(null)
    try {
      await claimCompetitionAward(current.id)
      await refreshUser?.()
      setQueue((prev) => prev.filter((row) => row.id !== current.id))
    } catch {
      setError('Could not add your Stars right now. Please try again.')
    } finally {
      setBusy(false)
    }
  }, [busy, current, refreshUser])

  if (!current) return null

  return (
    <ConfirmDialog
      title="You won a weekly award"
      busy={busy}
      actions={[
        {
          label: busy ? 'Receiving…' : `Receive ${current.stars_amount} Stars`,
          variant: 'primary',
          disabled: busy,
          onClick: () => void onReceive(),
        },
      ]}
    >
      <p data-testid="weekly-award-claim-body">
        Congratulations — you placed in <strong>{current.label}</strong> for {current.week_label}.
        Confirm below to add <strong>{current.stars_amount} Stars</strong> to your balance.
      </p>
      {error ? (
        <p role="alert" data-testid="weekly-award-claim-error">
          {error}
        </p>
      ) : null}
    </ConfirmDialog>
  )
}
