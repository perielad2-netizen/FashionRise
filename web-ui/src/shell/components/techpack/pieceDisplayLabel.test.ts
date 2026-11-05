import { describe, expect, it } from 'vitest'
import { pieceDisplayLabel, pieceRoleLabel } from '@/shell/components/techpack/pieceHelpers'
import type { TechpackPiece } from '@/services/techpacksApi'

function piece(partial: Partial<TechpackPiece> & Pick<TechpackPiece, 'id' | 'category' | 'label'>): TechpackPiece {
  return {
    materials: {},
    closures: {},
    fit: {},
    finished_measurements: {},
    ...partial,
  }
}

describe('pieceDisplayLabel', () => {
  it('formats lavender hoodie + yellow shorts without TOP — TOP', () => {
    const top = piece({
      id: '1',
      category: 'top',
      label: 'TOP',
      color_hint: 'lavender-purple',
    })
    const bottom = piece({
      id: '2',
      category: 'shorts',
      label: 'SHORTS',
      color_hint: 'golden-yellow',
    })
    expect(pieceRoleLabel('top')).toBe('Top')
    expect(pieceRoleLabel('shorts')).toBe('Bottom')
    expect(pieceDisplayLabel(top)).toBe('Top — Lavender Purple Top')
    expect(pieceDisplayLabel(bottom)).toBe('Bottom — Golden Yellow Shorts')
    expect(pieceDisplayLabel(top)).not.toMatch(/TOP — TOP/i)
    expect(pieceDisplayLabel(bottom)).not.toMatch(/SHORTS — SHORTS/i)
  })

  it('keeps a distinctive designer label', () => {
    const p = piece({
      id: '1',
      category: 'shirt',
      label: 'Lavender Hoodie',
      color_hint: 'lavender',
    })
    expect(pieceDisplayLabel(p)).toBe('Top — Lavender Hoodie')
  })
})
