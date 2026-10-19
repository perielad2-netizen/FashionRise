import { describe, expect, it } from 'vitest'
import { matchStudioShortcut } from '@/lib/studioShortcuts'

const base = {
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  altKey: false,
  target: null,
}

describe('matchStudioShortcut', () => {
  it('maps the advertised beta shortcuts', () => {
    expect(matchStudioShortcut({ ...base, key: 'b' })).toBe('draw')
    expect(matchStudioShortcut({ ...base, key: 'E' })).toBe('erase')
    expect(matchStudioShortcut({ ...base, key: 'z', ctrlKey: true })).toBe('undo')
    expect(matchStudioShortcut({ ...base, key: 'z', metaKey: true, shiftKey: true })).toBe('redo')
    expect(matchStudioShortcut({ ...base, key: 'y', ctrlKey: true })).toBe('redo')
  })

  it('ignores shortcuts while typing and unrelated keys', () => {
    const input = document.createElement('input')
    expect(matchStudioShortcut({ ...base, key: 'b', target: input })).toBeNull()
    expect(matchStudioShortcut({ ...base, key: 'k' })).toBeNull()
    expect(matchStudioShortcut({ ...base, key: 'b', altKey: true })).toBeNull()
  })
})