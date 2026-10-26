import { describe, expect, it } from 'vitest'
import { normalizeSideBag } from '@/lib/studioSideArtwork'

describe('normalizeSideBag', () => {
  it('accepts omitted fills as empty', () => {
    expect(normalizeSideBag({ strokes: [] })).toEqual({ strokes: [], fills: [] })
  })

  it('rejects non-array fills instead of coercing to []', () => {
    expect(normalizeSideBag({ strokes: [], fills: 'nope' })).toBeNull()
    expect(normalizeSideBag({ strokes: [], fills: {} })).toBeNull()
  })

  it('rejects non-array strokes', () => {
    expect(normalizeSideBag({ strokes: 'x', fills: [] })).toBeNull()
  })
})
