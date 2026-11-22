import { useEffect, useState } from 'react'
import { Share2, UserRound } from 'lucide-react'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { ApiError } from '@/services/api/client'
import { listFriends, type Friendship } from '@/services/friendsApi'
import { shareDesignWithFriend } from '@/services/designShareApi'
import type { SavedDesignRecord } from '@/lib/savedDesign'
import styles from './ShareDesignDialog.module.css'

type Props = {
  record: SavedDesignRecord
  onClose: () => void
  onShared: (message: string) => void
}

type Phase = 'loading' | 'pick' | 'sending' | 'error'

export function ShareDesignDialog({ record, onClose, onShared }: Props) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [friends, setFriends] = useState<Friendship[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const title = record.title || 'Untitled design'

  useEffect(() => {
    const controller = new AbortController()
    listFriends(controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return
        const accepted = rows.filter((r) => r.status === 'accepted')
        setFriends(accepted)
        setPhase('pick')
        if (accepted.length === 1) setSelectedId(accepted[0].friend.user_id)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(
          err instanceof ApiError
            ? err.message
            : 'Could not load friends. Check your connection and try again.',
        )
        setPhase('error')
      })
    return () => controller.abort()
  }, [])

  const send = async () => {
    if (!selectedId || phase === 'sending') return
    setPhase('sending')
    setError(null)
    try {
      const result = await shareDesignWithFriend(record.id, selectedId)
      onShared(result.message)
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Could not share this design. Try again.',
      )
      setPhase('error')
    }
  }

  return (
    <ConfirmDialog
      title={`Share “${title}”`}
      busy={phase === 'sending' || phase === 'loading'}
      onEscape={phase === 'sending' ? undefined : onClose}
      actions={
        phase === 'error' && friends.length === 0
          ? [{ label: 'Close', onClick: onClose, variant: 'ghost' }]
          : [
              {
                label: 'Cancel',
                onClick: onClose,
                variant: 'ghost',
                disabled: phase === 'sending',
              },
              {
                label: phase === 'sending' ? 'Sending…' : 'Send to friend',
                onClick: () => void send(),
                variant: 'primary',
                disabled: phase === 'sending' || phase === 'loading' || !selectedId,
              },
            ]
      }
    >
      <div className={styles.body}>
        <p className={styles.lead}>
          Your friend gets a copy they can continue in Studio, with access to your fabrics and
          models. They can Magic, publish to FashionRise, and send it back anytime.
        </p>

        {phase === 'loading' ? (
          <p className={styles.status} role="status">
            Loading friends…
          </p>
        ) : null}

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}

        {friends.length === 0 && phase !== 'loading' ? (
          <p className={styles.empty}>
            Add a friend in Runway → Manage friends first, then share a design.
          </p>
        ) : (
          <ul className={styles.list} aria-label="Friends">
            {friends.map((row) => {
              const friend = row.friend
              const selected = selectedId === friend.user_id
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    className={selected ? styles.friendSelected : styles.friend}
                    onClick={() => setSelectedId(friend.user_id)}
                    disabled={phase === 'sending'}
                    aria-pressed={selected}
                  >
                    <span className={styles.avatar} aria-hidden="true">
                      {friend.avatar_url ? (
                        <img src={friend.avatar_url} alt="" />
                      ) : (
                        <UserRound size={18} />
                      )}
                    </span>
                    <span className={styles.friendCopy}>
                      <strong>{friend.display_name || friend.username}</strong>
                      <span>@{friend.username}</span>
                    </span>
                    {selected ? <Share2 size={16} aria-hidden="true" /> : null}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </ConfirmDialog>
  )
}
