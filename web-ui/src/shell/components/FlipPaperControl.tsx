import { useCallback, useState } from 'react'
import type { StudioPaperSide } from '@/lib/studioSideArtwork'
import styles from './FlipPaperControl.module.css'

type Props = {
  activeSide: StudioPaperSide
  rearAvailable: boolean
  onSideChange: (side: StudioPaperSide) => void
  compact?: boolean
}

export function FlipPaperControl({
  activeSide,
  rearAvailable,
  onSideChange,
  compact = false,
}: Props) {
  const [animating, setAnimating] = useState(false)

  const flip = useCallback(() => {
    if (!rearAvailable) return
    setAnimating(true)
    window.setTimeout(() => setAnimating(false), 420)
    onSideChange(activeSide === 'front' ? 'back' : 'front')
  }, [activeSide, onSideChange, rearAvailable])

  return (
    <div
      className={`${styles.wrap} ${compact ? styles.compact : ''} ${animating ? styles.animating : ''}`}
      data-testid="flip-paper-control"
    >
      <div className={styles.segmented} role="group" aria-label="Paper side">
        <button
          type="button"
          className={activeSide === 'front' ? styles.segActive : styles.seg}
          aria-pressed={activeSide === 'front'}
          onClick={() => onSideChange('front')}
        >
          Front
        </button>
        <button
          type="button"
          className={activeSide === 'back' ? styles.segActive : styles.seg}
          aria-pressed={activeSide === 'back'}
          disabled={!rearAvailable}
          title={rearAvailable ? 'Back croquis' : 'No back view for this model'}
          onClick={() => rearAvailable && onSideChange('back')}
        >
          Back
        </button>
      </div>
      {rearAvailable ? (
        <button type="button" className={styles.flipBtn} onClick={flip} aria-label="Flip paper">
          Flip
        </button>
      ) : null}
      <div className={styles.paperCue} aria-hidden="true">
        <span className={styles.paperFront} />
        <span className={styles.paperBack} />
      </div>
    </div>
  )
}
