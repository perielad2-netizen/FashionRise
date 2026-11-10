import { useCallback } from 'react'
import type { StudioPaperSide } from '@/lib/studioSideArtwork'
import styles from './FlipPaperControl.module.css'

const DEFAULT_UNAVAILABLE =
  'Back view is not available for this model. Keep sketching on the Front.'

type Props = {
  activeSide: StudioPaperSide
  rearAvailable: boolean
  onSideChange: (side: StudioPaperSide) => void
  /** Honest explanation when Back cannot be opened (atelier / missing asset). */
  unavailableReason?: string
  /** Optional notice when the user activates Back while unavailable. */
  onUnavailableFlip?: (reason: string) => void
  /** Visual density for immersive paper chrome. */
  compact?: boolean
}

/**
 * Paper-corner Front / Back segmented toggle (replaces the old rotate icon).
 */
export function FlipPaperControl({
  activeSide,
  rearAvailable,
  onSideChange,
  unavailableReason = DEFAULT_UNAVAILABLE,
  onUnavailableFlip,
  compact = false,
}: Props) {
  const selectSide = useCallback(
    (side: StudioPaperSide) => {
      if (side === activeSide) return
      if (side === 'back' && !rearAvailable) {
        onUnavailableFlip?.(unavailableReason)
        return
      }
      onSideChange(side)
    },
    [activeSide, onSideChange, onUnavailableFlip, rearAvailable, unavailableReason],
  )

  const backTitle = !rearAvailable
    ? unavailableReason
    : activeSide === 'back'
      ? 'Back view'
      : 'Show Back'
  const backAria = !rearAvailable
    ? `Back unavailable. ${unavailableReason}`
    : 'Back'

  return (
    <div
      className={`${styles.wrap} ${compact ? styles.compact : ''} ${
        !rearAvailable ? styles.unavailable : ''
      }`}
      role="group"
      aria-label="Paper side"
      data-testid="flip-paper-control"
      data-side={activeSide}
      data-rear-available={rearAvailable ? 'true' : 'false'}
    >
      <button
        type="button"
        className={activeSide === 'front' ? styles.segActive : styles.seg}
        onClick={() => selectSide('front')}
        title="Front view"
        aria-label="Front"
        aria-pressed={activeSide === 'front'}
        data-testid="flip-paper-front"
      >
        Front
      </button>
      <button
        type="button"
        className={
          activeSide === 'back'
            ? styles.segActive
            : !rearAvailable
              ? `${styles.seg} ${styles.segDisabled}`
              : styles.seg
        }
        onClick={() => selectSide('back')}
        title={backTitle}
        aria-label={backAria}
        aria-pressed={activeSide === 'back'}
        aria-disabled={!rearAvailable}
        data-testid="flip-paper-button"
      >
        Back
      </button>
    </div>
  )
}
