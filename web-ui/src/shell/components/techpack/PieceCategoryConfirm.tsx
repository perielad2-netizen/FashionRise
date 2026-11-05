import type { TechpackPiece } from '@/services/techpacksApi'
import {
  FRIENDLY_CATEGORY_CHOICES,
  isInconclusivePiece,
  retargetFinishedMeasurements,
} from '@/shell/components/techpack/pieceHelpers'
import styles from './PieceCategoryConfirm.module.css'

type Props = {
  pieces: TechpackPiece[]
  units?: string
  disabled?: boolean
  onConfirm: (pieceId: string, next: TechpackPiece) => void
}

export function PieceCategoryConfirm({
  pieces,
  units = 'cm',
  disabled = false,
  onConfirm,
}: Props) {
  const pending = pieces.filter(isInconclusivePiece)
  if (!pending.length) return null

  return (
    <div className={styles.card} data-testid="piece-category-confirm">
      <h3 className={styles.title}>What did you design?</h3>
      <p className={styles.lead}>
        Tap a garment type so AI can build the technical pack. You can refine details later.
      </p>
      {pending.map((piece) => (
        <div key={piece.id} className={styles.pieceBlock}>
          {pending.length > 1 ? (
            <p className={styles.pieceName}>{piece.label || 'Garment'}</p>
          ) : null}
          <div className={styles.chipRow} role="listbox" aria-label="Garment type">
            {FRIENDLY_CATEGORY_CHOICES.map((choice) => (
              <button
                key={choice.id}
                type="button"
                role="option"
                className={styles.chip}
                disabled={disabled}
                onClick={() => {
                  const next = retargetFinishedMeasurements(piece, choice.id, units)
                  onConfirm(piece.id, {
                    ...next,
                    label: choice.label,
                    role: choice.id,
                  })
                }}
              >
                {choice.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
