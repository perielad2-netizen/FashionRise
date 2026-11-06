import { describe, expect, it } from 'vitest'
import {
  createEmptyPiece,
  isInconclusivePiece,
  retargetFinishedMeasurements,
} from './pieceHelpers'

describe('isInconclusivePiece', () => {
  it('flags confirm-category fallback pieces', () => {
    const piece = createEmptyPiece({
      category: 'other',
      label: 'Garment (confirm category)',
    })
    piece.detection_source = 'heuristic_fallback'
    expect(isInconclusivePiece(piece)).toBe(true)
  })

  it('clears after designer category confirm', () => {
    const piece = createEmptyPiece({
      category: 'other',
      label: 'Garment (confirm category)',
    })
    piece.detection_source = 'heuristic_fallback'
    const confirmed = retargetFinishedMeasurements(piece, 'top', 'cm')
    expect(isInconclusivePiece(confirmed)).toBe(false)
    expect(confirmed.category_user_confirmed).toBe(true)
  })
})
