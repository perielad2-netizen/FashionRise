/** Garment region fills (solid, gradient, fabric) stored alongside ink strokes. */

export type SolidFillStyle = { kind: 'solid'; color: string }

export type GradientFillStyle = {
  kind: 'gradient'
  gradientId: string
  colors: [string, string]
  /** Degrees; 0 = left→right, 90 = top→bottom. */
  angle: number
}

export type FabricFillStyle = {
  kind: 'fabric'
  fabricId: string
}

export type FillStyle = SolidFillStyle | GradientFillStyle | FabricFillStyle

export type FillOp = {
  id: string
  /** Closed polygon in design space: [x0,y0,x1,y1,...], at least 3 points. */
  contour: number[]
  style: FillStyle
  /** Seed click used to create the fill (for debugging / UX). */
  seedX: number
  seedY: number
}

export type FashionPaletteSwatch = {
  id: string
  label: string
  color: string
}

/** Practical fashion inks beyond the default monochrome set. */
export const FASHION_PALETTE: FashionPaletteSwatch[] = [
  { id: 'ivory', label: 'Ivory', color: '#F5F0E6' },
  { id: 'blush', label: 'Blush', color: '#E8A0A8' },
  { id: 'crimson', label: 'Crimson', color: '#B91C1C' },
  { id: 'coral', label: 'Coral', color: '#F97316' },
  { id: 'gold', label: 'Gold', color: '#D4A017' },
  { id: 'olive', label: 'Olive', color: '#6B7280' },
  { id: 'forest', label: 'Forest', color: '#166534' },
  { id: 'teal', label: 'Teal', color: '#0F766E' },
  { id: 'sky', label: 'Sky', color: '#38BDF8' },
  { id: 'royal', label: 'Royal', color: '#1D4ED8' },
  { id: 'lilac', label: 'Lilac', color: '#A78BFA' },
  { id: 'black', label: 'Black', color: '#111111' },
]

export type FabricPreset = {
  id: string
  label: string
  /** CSS preview for the panel swatch. */
  preview: string
}

export const FABRIC_PRESETS: FabricPreset[] = [
  {
    id: 'satin',
    label: 'Satin',
    preview: 'linear-gradient(135deg,#fff7fb 0%,#f9a8d4 40%,#be185d 70%,#fff1f8 100%)',
  },
  {
    id: 'denim',
    label: 'Denim',
    preview: 'linear-gradient(145deg,#93c5fd,#1e3a8a 55%,#172554)',
  },
  {
    id: 'cotton',
    label: 'Cotton',
    preview: 'linear-gradient(145deg,#f5e6d3,#e7d3b8 50%,#c4a484)',
  },
  {
    id: 'lace',
    label: 'Lace',
    preview: 'radial-gradient(circle at 30% 30%,#fff 0 2px,transparent 3px),#fce7f3',
  },
  {
    id: 'floral',
    label: 'Floral',
    preview: 'radial-gradient(circle at 35% 40%,#fb7185 0 4px,transparent 5px),#fef3c7',
  },
  {
    id: 'sequins',
    label: 'Sequins',
    preview: 'radial-gradient(circle at 40% 40%,#fde68a 0 3px,#b45309 4px,transparent 5px),#7c2d12',
  },
]

export type GradientPreset = {
  id: string
  label: string
  colors: [string, string]
  angle: number
  preview: string
}

export const GRADIENT_PRESETS: GradientPreset[] = [
  {
    id: 'rose-violet',
    label: 'Rose violet',
    colors: ['#D63384', '#7C3AED'],
    angle: 135,
    preview: 'linear-gradient(135deg,#d63384,#7c3aed)',
  },
  {
    id: 'champagne',
    label: 'Champagne',
    colors: ['#F8F4F0', '#D4AF9B'],
    angle: 135,
    preview: 'linear-gradient(135deg,#f8f4f0,#d4af9b)',
  },
  {
    id: 'ocean-blush',
    label: 'Ocean blush',
    colors: ['#0EA5E9', '#D63384'],
    angle: 135,
    preview: 'linear-gradient(135deg,#0ea5e9,#d63384)',
  },
  {
    id: 'noir-wine',
    label: 'Noir wine',
    colors: ['#111827', '#9F1239'],
    angle: 135,
    preview: 'linear-gradient(135deg,#111827,#9f1239)',
  },
]

export function createFillId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `fill_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function cloneFills(fills: FillOp[]): FillOp[] {
  return fills.map((f) => ({
    ...f,
    contour: [...f.contour],
    style: { ...f.style, ...(f.style.kind === 'gradient' ? { colors: [...f.style.colors] as [string, string] } : {}) },
  }))
}

export function contourToSvgPath(contour: number[]): string {
  if (contour.length < 6) return ''
  let d = `M ${contour[0]} ${contour[1]}`
  for (let i = 2; i < contour.length; i += 2) {
    d += ` L ${contour[i]} ${contour[i + 1]}`
  }
  return `${d} Z`
}

export function parseFillOp(raw: unknown): FillOp | null {
  if (!raw || typeof raw !== 'object') return null
  const f = raw as Partial<FillOp>
  if (!Array.isArray(f.contour) || f.contour.length < 6) return null
  const contour = f.contour.filter((n) => typeof n === 'number')
  if (contour.length < 6 || contour.length % 2 !== 0) return null
  const style = parseFillStyle(f.style)
  if (!style) return null
  return {
    id: typeof f.id === 'string' && f.id ? f.id : createFillId(),
    contour,
    style,
    seedX: typeof f.seedX === 'number' ? f.seedX : contour[0]!,
    seedY: typeof f.seedY === 'number' ? f.seedY : contour[1]!,
  }
}

function parseFillStyle(raw: unknown): FillStyle | null {
  if (!raw || typeof raw !== 'object') return null
  const s = raw as Record<string, unknown>
  if (s.kind === 'solid' && typeof s.color === 'string' && /^#[0-9a-fA-F]{6}$/i.test(s.color)) {
    return { kind: 'solid', color: s.color.toUpperCase() }
  }
  if (
    s.kind === 'gradient' &&
    typeof s.gradientId === 'string' &&
    Array.isArray(s.colors) &&
    s.colors.length >= 2 &&
    typeof s.colors[0] === 'string' &&
    typeof s.colors[1] === 'string'
  ) {
    return {
      kind: 'gradient',
      gradientId: s.gradientId,
      colors: [String(s.colors[0]).toUpperCase(), String(s.colors[1]).toUpperCase()],
      angle: typeof s.angle === 'number' ? s.angle : 135,
    }
  }
  if (s.kind === 'fabric' && typeof s.fabricId === 'string') {
    const known = FABRIC_PRESETS.some((p) => p.id === s.fabricId)
    if (!known) return null
    return { kind: 'fabric', fabricId: s.fabricId }
  }
  return null
}

export function solidStyle(color: string): SolidFillStyle {
  return { kind: 'solid', color: color.toUpperCase() }
}

export function fabricStyle(fabricId: string): FabricFillStyle | null {
  if (!FABRIC_PRESETS.some((p) => p.id === fabricId)) return null
  return { kind: 'fabric', fabricId }
}

export function gradientStyleFromPreset(id: string): GradientFillStyle | null {
  const preset = GRADIENT_PRESETS.find((g) => g.id === id)
  if (!preset) return null
  return {
    kind: 'gradient',
    gradientId: preset.id,
    colors: [...preset.colors] as [string, string],
    angle: preset.angle,
  }
}
