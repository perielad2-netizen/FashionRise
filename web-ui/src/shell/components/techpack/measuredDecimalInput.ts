import type { MeasuredValue } from '@/services/techpacksApi'

/**
 * Decimal measurement edit helpers.
 *
 * Controlled inputs must not feed intermediate strings through `Number(raw)` —
 * `Number("25.") === 25` collapses the separator while typing. Keep a local
 * buffer for in-progress text; only commit complete parses on change/blur.
 */

/** Dot or locale-comma decimal buffer (optional leading minus). */
const BUFFER_RE = /^-?\d*(?:[.,]\d*)?$/

export function formatCommittedDisplay(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return ''
    // String(n) keeps JS number precision; no toFixed truncation.
    return String(value)
  }
  return String(value)
}

export function isAllowedDecimalBuffer(raw: string): boolean {
  return BUFFER_RE.test(raw)
}

export type ParseMeasuredResult =
  | { kind: 'empty' }
  | { kind: 'valid'; value: number }
  | { kind: 'invalid' }

/** Normalize a single locale decimal comma to a dot for parsing. */
export function normalizeDecimalSeparators(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed.includes(',')) return trimmed
  // Treat the first comma as the decimal mark when there is no dot.
  if (!trimmed.includes('.')) {
    const idx = trimmed.indexOf(',')
    return `${trimmed.slice(0, idx)}.${trimmed.slice(idx + 1).replace(/,/g, '')}`
  }
  // Mixed separators → invalid shape for our buffer (caller treats as invalid).
  return trimmed
}

export function parseMeasuredInput(raw: string): ParseMeasuredResult {
  const trimmed = raw.trim()
  if (trimmed === '') return { kind: 'empty' }

  if (!isAllowedDecimalBuffer(trimmed)) return { kind: 'invalid' }

  const normalized = normalizeDecimalSeparators(trimmed)
  if (normalized.includes(',')) return { kind: 'invalid' }

  // Incomplete fragments that Number() would wrongly coerce (e.g. Number("")===0).
  if (normalized === '.' || normalized === '-' || normalized === '-.') {
    return { kind: 'invalid' }
  }

  // Reject hex / binary forms Number() accepts.
  if (/^[-+]?0[xXbB]/.test(normalized)) return { kind: 'invalid' }

  const n = Number(normalized)
  if (!Number.isFinite(n)) return { kind: 'invalid' }
  return { kind: 'valid', value: n }
}

/**
 * True when the buffer is a finished empty/number commit (not trailing separators).
 * `"25."` / `"0,"` / `"."` stay local until the user continues or blurs.
 */
export function isCompleteMeasuredInput(raw: string): boolean {
  const trimmed = raw.trim()
  if (trimmed === '') return true
  if (/[.,]$/.test(trimmed)) return false
  if (trimmed === '-' || trimmed === '.' || trimmed === ',' || trimmed === '-.' || trimmed === '-,') {
    return false
  }
  return parseMeasuredInput(trimmed).kind === 'valid'
}

/**
 * Build the next MeasuredValue from a draft buffer.
 * Returns null when the draft is invalid — caller keeps prior committed value
 * and reverts the display (never coerce invalid → 0).
 *
 * User edits always set `source: 'designer'` (including prior AI/calculated).
 * Empty clears to `null` + `source: 'empty'`. Does not alter review_status
 * (no automatic manufacturing approval).
 */
export function commitMeasuredEdit(
  prev: MeasuredValue,
  raw: string,
): MeasuredValue | null {
  const parsed = parseMeasuredInput(raw)
  if (parsed.kind === 'invalid') return null

  const unit = prev.unit || 'cm'

  if (parsed.kind === 'empty') {
    return {
      ...prev,
      value: null,
      source: 'empty',
      unit,
    }
  }

  return {
    ...prev,
    value: parsed.value,
    source: 'designer',
    unit,
  }
}
