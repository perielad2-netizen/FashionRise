import { useCallback, useState } from 'react'
import { RotateCw } from 'lucide-react'
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
  /** Optional notice when the user activates Flip while Back is unavailable. */
  onUnavailableFlip?: (reason: string) => void
  /** Visual density for immersive paper chrome. */
  compact?: boolean
}

/**
 * Paper-corner Front/Back control. Icon-only on the cream paper; side is
 * exposed via aria-label / data-side (no visible FRONT/BACK text).
 */
export function FlipPaperControl({
  activeSide,
  rearAvailable,
  onSideChange,
  unavailableReason = DEFAULT_UNAVAILABLE,
  onUnavailableFlip,
  compact = false,
}: Props) {
  const [animating, setAnimating] = useState(false)
  const tooltip = !rearAvailable
    ? unavailableReason
    : activeSide === 'front'
      ? 'Flip to Back'
      : 'Flip to Front'
  const ariaLabel = !rearAvailable
    ? `Flip paper unavailable. ${unavailableReason}`
    : activeSide === 'front'
      ? 'Flip to Back'
      : 'Flip to Front'

  const flip = useCallback(() => {
    if (!rearAvailable) {
      onUnavailableFlip?.(unavailableReason)
      return
    }
    setAnimating(true)
    window.setTimeout(() => setAnimating(false), 420)
    onSideChange(activeSide === 'front' ? 'back' : 'front')
  }, [activeSide, onSideChange, onUnavailableFlip, rearAvailable, unavailableReason])

  return (
    <div
      className={`${styles.wrap} ${compact ? styles.compact : ''} ${animating ? styles.animating : ''} ${
        !rearAvailable ? styles.unavailable : ''
      }`}
      data-testid="flip-paper-control"
      data-side={activeSide}
      data-rear-available={rearAvailable ? 'true' : 'false'}
    >
      <button
        type="button"
        className={styles.flipBtn}
        onClick={flip}
        title={tooltip}
        aria-label={ariaLabel}
        data-testid="flip-paper-button"
      >
        <RotateCw size={compact ? 16 : 18} strokeWidth={1.85} aria-hidden="true" />
      </button>
      {/* Decorative cue only — never applied to canvas ink/reference. */}
      <div className={styles.paperCue} aria-hidden="true">
        <span className={styles.paperFront} />
        <span className={styles.paperBack} />
      </div>
    </div>
  )
}
