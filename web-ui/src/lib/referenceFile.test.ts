import { describe, expect, it } from 'vitest'
import { isAllowedReferenceMime, validateReferenceImageFile } from '@/lib/referenceFile'

describe('reference MIME validation', () => {
  it('accepts jpeg/png/webp', () => {
    expect(isAllowedReferenceMime('image/jpeg')).toBe(true)
    expect(isAllowedReferenceMime('image/png')).toBe(true)
    expect(isAllowedReferenceMime('image/webp')).toBe(true)
  })

  it('rejects other types', () => {
    expect(isAllowedReferenceMime('image/gif')).toBe(false)
    expect(isAllowedReferenceMime('application/pdf')).toBe(false)
    expect(isAllowedReferenceMime('')).toBe(false)
  })

  it('validateReferenceImageFile returns friendly error', () => {
    const file = new File(['x'], 'x.gif', { type: 'image/gif' })
    const result = validateReferenceImageFile(file)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.message).toMatch(/JPEG, PNG, or WebP/i)
    }
  })

  it('validateReferenceImageFile accepts png', () => {
    const file = new File(['x'], 'x.png', { type: 'image/png' })
    expect(validateReferenceImageFile(file)).toEqual({ ok: true })
  })
})
