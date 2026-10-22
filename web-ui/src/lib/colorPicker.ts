export type Rgb = { r: number; g: number; b: number }
export type Hsv = { h: number; s: number; v: number }

const HEX6 = /^#?([0-9a-fA-F]{6})$/

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

export function normalizeHex(raw: string): string | null {
  const m = HEX6.exec(raw.trim())
  if (!m) return null
  return `#${m[1]!.toUpperCase()}`
}

export function rgbToHex({ r, g, b }: Rgb): string {
  const to = (n: number) => clamp(Math.round(n), 0, 255).toString(16).padStart(2, '0')
  return `#${to(r)}${to(g)}${to(b)}`.toUpperCase()
}

export function hexToRgb(hex: string): Rgb | null {
  const normalized = normalizeHex(hex)
  if (!normalized) return null
  const n = Number.parseInt(normalized.slice(1), 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

/** RGB 0–255 → HSV with h in [0, 360), s/v in [0, 1]. */
export function rgbToHsv({ r, g, b }: Rgb): Hsv {
  const rr = r / 255
  const gg = g / 255
  const bb = b / 255
  const max = Math.max(rr, gg, bb)
  const min = Math.min(rr, gg, bb)
  const d = max - min
  let h = 0
  if (d !== 0) {
    if (max === rr) h = ((gg - bb) / d) % 6
    else if (max === gg) h = (bb - rr) / d + 2
    else h = (rr - gg) / d + 4
    h *= 60
    if (h < 0) h += 360
  }
  const s = max === 0 ? 0 : d / max
  return { h, s, v: max }
}

/** HSV → RGB 0–255. */
export function hsvToRgb({ h, s, v }: Hsv): Rgb {
  const hh = ((h % 360) + 360) % 360
  const c = v * s
  const x = c * (1 - Math.abs(((hh / 60) % 2) - 1))
  const m = v - c
  let rr = 0
  let gg = 0
  let bb = 0
  if (hh < 60) {
    rr = c
    gg = x
  } else if (hh < 120) {
    rr = x
    gg = c
  } else if (hh < 180) {
    gg = c
    bb = x
  } else if (hh < 240) {
    gg = x
    bb = c
  } else if (hh < 300) {
    rr = x
    bb = c
  } else {
    rr = c
    bb = x
  }
  return {
    r: Math.round((rr + m) * 255),
    g: Math.round((gg + m) * 255),
    b: Math.round((bb + m) * 255),
  }
}

export function hexToHsv(hex: string): Hsv | null {
  const rgb = hexToRgb(hex)
  return rgb ? rgbToHsv(rgb) : null
}

export function hsvToHex(hsv: Hsv): string {
  return rgbToHex(hsvToRgb(hsv))
}

/** Pure hue at full saturation/value — for SV square background. */
export function hueToCss(h: number): string {
  return hsvToHex({ h, s: 1, v: 1 })
}
