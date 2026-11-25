import { describe, expect, it } from 'vitest'
import { parsePositiveGrantAmount } from './adminApi'

describe('parsePositiveGrantAmount', () => {
  it('accepts positive integers', () => {
    expect(parsePositiveGrantAmount('1')).toBe(1)
    expect(parsePositiveGrantAmount('50')).toBe(50)
    expect(parsePositiveGrantAmount('10000')).toBe(10000)
  })

  it('rejects zero, negative, decimals, and junk', () => {
    expect(parsePositiveGrantAmount('0')).toBeNull()
    expect(parsePositiveGrantAmount('-1')).toBeNull()
    expect(parsePositiveGrantAmount('1.5')).toBeNull()
    expect(parsePositiveGrantAmount('10.0')).toBeNull()
    expect(parsePositiveGrantAmount('')).toBeNull()
    expect(parsePositiveGrantAmount('abc')).toBeNull()
    expect(parsePositiveGrantAmount('01')).toBeNull()
    expect(parsePositiveGrantAmount('1e2')).toBeNull()
  })
})
