import { describe, expect, it } from 'vitest'
import type { MeasuredValue } from '@/services/techpacksApi'
import {
  commitMeasuredEdit,
  formatCommittedDisplay,
  isAllowedDecimalBuffer,
  isCompleteMeasuredInput,
  parseMeasuredInput,
} from './measuredDecimalInput'

function mv(partial: Partial<MeasuredValue> = {}): MeasuredValue {
  return {
    value: null,
    unit: 'cm',
    source: 'empty',
    review_status: 'open',
    ...partial,
  }
}

describe('measuredDecimalInput buffer', () => {
  it('allows intermediate decimal buffers including locale comma', () => {
    for (const s of ['', '25', '25.', '0.', '.5', '25.5', '25,', '25,5', ',5', '-1.2', '12.345678']) {
      expect(isAllowedDecimalBuffer(s), s).toBe(true)
    }
    for (const s of ['25.5.5', '12a', '1e2', '0x10', '25..', '1,2,3']) {
      expect(isAllowedDecimalBuffer(s), s).toBe(false)
    }
  })

  it('treats trailing separators as incomplete (not yet committed)', () => {
    expect(isCompleteMeasuredInput('25.')).toBe(false)
    expect(isCompleteMeasuredInput('0,')).toBe(false)
    expect(isCompleteMeasuredInput('.')).toBe(false)
    expect(isCompleteMeasuredInput('')).toBe(true)
    expect(isCompleteMeasuredInput('25.5')).toBe(true)
    expect(isCompleteMeasuredInput('25,5')).toBe(true)
    expect(isCompleteMeasuredInput('.5')).toBe(true)
  })
})

describe('parseMeasuredInput', () => {
  it('parses empty, decimals, and locale commas without integer truncation', () => {
    expect(parseMeasuredInput('')).toEqual({ kind: 'empty' })
    expect(parseMeasuredInput('  ')).toEqual({ kind: 'empty' })
    expect(parseMeasuredInput('25.5')).toEqual({ kind: 'valid', value: 25.5 })
    expect(parseMeasuredInput('25,5')).toEqual({ kind: 'valid', value: 25.5 })
    expect(parseMeasuredInput('.5')).toEqual({ kind: 'valid', value: 0.5 })
    expect(parseMeasuredInput('12.3456789')).toEqual({ kind: 'valid', value: 12.3456789 })
    // Trailing separator is numeric via Number, but commit path uses completeness separately.
    expect(parseMeasuredInput('25.')).toEqual({ kind: 'valid', value: 25 })
  })

  it('rejects invalid input instead of coercing to 0', () => {
    expect(parseMeasuredInput('.')).toEqual({ kind: 'invalid' })
    expect(parseMeasuredInput('-')).toEqual({ kind: 'invalid' })
    expect(parseMeasuredInput('abc')).toEqual({ kind: 'invalid' })
    expect(parseMeasuredInput('0x10')).toEqual({ kind: 'invalid' })
    expect(parseMeasuredInput('25.5.1')).toEqual({ kind: 'invalid' })
  })
})

describe('commitMeasuredEdit provenance', () => {
  it('clears empty fields to null + source empty and preserves review_status', () => {
    const prev = mv({
      value: 88,
      source: 'ai',
      review_status: 'open',
      note: 'keep-me',
    })
    const next = commitMeasuredEdit(prev, '')
    expect(next).toEqual({
      ...prev,
      value: null,
      source: 'empty',
      unit: 'cm',
    })
    expect(next?.review_status).toBe('open')
  })

  it('marks AI and calculated edits as designer without manufacturing approval', () => {
    for (const source of ['ai', 'calculated', 'estimate'] as const) {
      const prev = mv({
        value: 40,
        source,
        review_status: 'open',
        assumptions: ['factory TBD'],
      })
      const next = commitMeasuredEdit(prev, '40.5')
      expect(next?.value).toBe(40.5)
      expect(next?.source).toBe('designer')
      expect(next?.review_status).toBe('open')
      expect(next?.assumptions).toEqual(['factory TBD'])
    }
  })

  it('returns null for invalid drafts so callers do not persist 0', () => {
    const prev = mv({ value: 10, source: 'ai' })
    expect(commitMeasuredEdit(prev, 'nope')).toBeNull()
    expect(commitMeasuredEdit(prev, '.')).toBeNull()
  })
})

describe('formatCommittedDisplay', () => {
  it('renders committed numbers without inventing values', () => {
    expect(formatCommittedDisplay(null)).toBe('')
    expect(formatCommittedDisplay(25.5)).toBe('25.5')
    expect(formatCommittedDisplay(0)).toBe('0')
    expect(formatCommittedDisplay('12.25')).toBe('12.25')
  })
})
