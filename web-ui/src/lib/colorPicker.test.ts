import { describe, expect, it } from 'vitest'
import {
  hexToHsv,
  hexToRgb,
  hsvToHex,
  hsvToRgb,
  normalizeHex,
  rgbToHex,
  rgbToHsv,
} from '@/lib/colorPicker'

describe('colorPicker conversions', () => {
  it('normalizes six-digit hex', () => {
    expect(normalizeHex('#a1b2c3')).toBe('#A1B2C3')
    expect(normalizeHex('ff00aa')).toBe('#FF00AA')
    expect(normalizeHex('#fff')).toBeNull()
    expect(normalizeHex('not-a-color')).toBeNull()
  })

  it('round-trips primary colors through HSV', () => {
    for (const hex of ['#FF0000', '#00FF00', '#0000FF', '#FFFFFF', '#000000', '#808080', '#C2185B']) {
      const rgb = hexToRgb(hex)!
      const hsv = rgbToHsv(rgb)
      expect(rgbToHex(hsvToRgb(hsv))).toBe(hex)
      expect(hsvToHex(hexToHsv(hex)!)).toBe(hex)
    }
  })

  it('keeps black and white at extremes', () => {
    expect(hexToHsv('#000000')).toMatchObject({ s: 0, v: 0 })
    expect(hexToHsv('#FFFFFF')).toMatchObject({ s: 0, v: 1 })
    expect(hsvToHex({ h: 200, s: 0, v: 0 })).toBe('#000000')
    expect(hsvToHex({ h: 200, s: 0, v: 1 })).toBe('#FFFFFF')
  })
})
