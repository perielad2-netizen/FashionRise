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

/** Designer-uploaded fabric referenced by private asset id (bytes stored server-side). */
export type UploadedFabricFillStyle = {
  kind: 'uploaded-fabric'
  assetId: string
  /** Tile scale relative to the source image (0.25–4). */
  scale: number
}

export type FillStyle = SolidFillStyle | GradientFillStyle | FabricFillStyle | UploadedFabricFillStyle

export const UPLOADED_FABRIC_SCALE_MIN = 0.25
export const UPLOADED_FABRIC_SCALE_MAX = 4
export const UPLOADED_FABRIC_SCALE_DEFAULT = 1

const ASSET_UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function clampUploadedFabricScale(raw: number): number {
  if (!Number.isFinite(raw)) return UPLOADED_FABRIC_SCALE_DEFAULT
  return Math.min(UPLOADED_FABRIC_SCALE_MAX, Math.max(UPLOADED_FABRIC_SCALE_MIN, raw))
}

export function isAssetId(value: string): boolean {
  return ASSET_UUID.test(value)
}

export type FillOp = {
  id: string
  /** Closed polygon in design space: [x0,y0,x1,y1,...], at least 3 points. */
  contour: number[]
  style: FillStyle
  /** Seed click used to create the fill (for debugging / UX). */
  seedX: number
  seedY: number
  /**
   * Stroke-list length when this fill was created. Eraser strokes at index >= this
   * punch the fill; earlier erasers do not (fill-after-erase chronology).
   * Missing on legacy saves → treat as 0 (all current erasers apply).
   */
  eraseAfterStrokeIndex?: number
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
  { id: 'olive', label: 'Olive', color: '#6B8E23' },
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

/**
 * Canvas/export angles: 0° = left→right, 90° = top→bottom (Y-down).
 * CSS linear-gradient uses 0° = upward, so preview CSS = canvasAngle + 90.
 */
export function gradientCssAngle(canvasAngleDeg: number): number {
  const a = ((canvasAngleDeg % 360) + 360) % 360
  return (a + 90) % 360
}

export function gradientPreviewCss(colors: [string, string], canvasAngleDeg: number): string {
  const deg = gradientCssAngle(canvasAngleDeg)
  return `linear-gradient(${deg}deg,${colors[0]},${colors[1]})`
}

export const CUSTOM_GRADIENT_ID = 'custom' as const

export function normalizeGradientAngle(raw: number): number {
  if (!Number.isFinite(raw)) return 135
  let a = raw % 360
  if (a < 0) a += 360
  return Math.round(a * 10) / 10
}

export function customGradientStyle(
  colors: [string, string],
  angle: number,
): GradientFillStyle | null {
  const c0 = colors[0]?.toUpperCase()
  const c1 = colors[1]?.toUpperCase()
  if (!c0 || !c1) return null
  if (!/^#[0-9A-F]{6}$/.test(c0) || !/^#[0-9A-F]{6}$/.test(c1)) return null
  return {
    kind: 'gradient',
    gradientId: CUSTOM_GRADIENT_ID,
    colors: [c0, c1],
    angle: normalizeGradientAngle(angle),
  }
}

export const GRADIENT_PRESETS: GradientPreset[] = [
  // Original four — ids, colors, angles, and legacy CSS preview strings unchanged.
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
  // WEB-V4G expansions — preview CSS uses canvas→CSS angle mapping.
  {
    id: 'rose-gold',
    label: 'Rose gold',
    colors: ['#F6C1B0', '#B76E79'],
    angle: 120,
    preview: gradientPreviewCss(['#F6C1B0', '#B76E79'], 120),
  },
  {
    id: 'sunset-coral',
    label: 'Sunset coral',
    colors: ['#FF8A5B', '#C2185B'],
    angle: 150,
    preview: gradientPreviewCss(['#FF8A5B', '#C2185B'], 150),
  },
  {
    id: 'golden-champagne',
    label: 'Golden champagne',
    colors: ['#FFF4D6', '#D4A017'],
    angle: 110,
    preview: gradientPreviewCss(['#FFF4D6', '#D4A017'], 110),
  },
  {
    id: 'sapphire-blue',
    label: 'Sapphire blue',
    colors: ['#60A5FA', '#1E3A8A'],
    angle: 160,
    preview: gradientPreviewCss(['#60A5FA', '#1E3A8A'], 160),
  },
  {
    id: 'turquoise-lagoon',
    label: 'Turquoise lagoon',
    colors: ['#5EEAD4', '#0F766E'],
    angle: 140,
    preview: gradientPreviewCss(['#5EEAD4', '#0F766E'], 140),
  },
  {
    id: 'emerald-mint',
    label: 'Emerald mint',
    colors: ['#A7F3D0', '#047857'],
    angle: 125,
    preview: gradientPreviewCss(['#A7F3D0', '#047857'], 125),
  },
  {
    id: 'burgundy-velvet',
    label: 'Burgundy velvet',
    colors: ['#E11D48', '#4C0519'],
    angle: 145,
    preview: gradientPreviewCss(['#E11D48', '#4C0519'], 145),
  },
  {
    id: 'midnight-violet',
    label: 'Midnight violet',
    colors: ['#C4B5FD', '#2E1065'],
    angle: 155,
    preview: gradientPreviewCss(['#C4B5FD', '#2E1065'], 155),
  },
  {
    id: 'peach-blush',
    label: 'Peach blush',
    colors: ['#FFE4D6', '#FB7185'],
    angle: 100,
    preview: gradientPreviewCss(['#FFE4D6', '#FB7185'], 100),
  },
  {
    id: 'lavender-haze',
    label: 'Lavender haze',
    colors: ['#EDE9FE', '#A78BFA'],
    angle: 130,
    preview: gradientPreviewCss(['#EDE9FE', '#A78BFA'], 130),
  },
  {
    id: 'silver-pearl',
    label: 'Silver pearl',
    colors: ['#F8FAFC', '#94A3B8'],
    angle: 90,
    preview: gradientPreviewCss(['#F8FAFC', '#94A3B8'], 90),
  },
  {
    id: 'black-cherry',
    label: 'Black cherry',
    colors: ['#7F1D1D', '#111827'],
    angle: 170,
    preview: gradientPreviewCss(['#7F1D1D', '#111827'], 170),
  },
]

/** Max flat contour values ([x,y,...]) accepted when parsing persisted fills. */
export const MAX_FILL_CONTOUR_VALUES = 4_000
/** Soft design-space pad: reject wildly out-of-range coordinates (malformed payloads). */
const DESIGN_PAD = 64
const CONTOUR_COORD_MIN = -DESIGN_PAD
const CONTOUR_COORD_MAX = 1024 + DESIGN_PAD

export function createFillId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `fill_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function cloneFills(fills: FillOp[]): FillOp[] {
  return fills.map((f) => {
    if (f.style.kind === 'gradient') {
      return {
        ...f,
        contour: [...f.contour],
        style: { ...f.style, colors: [...f.style.colors] as [string, string] },
      }
    }
    return {
      ...f,
      contour: [...f.contour],
      style: { ...f.style },
    }
  })
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
  // Reject oversized / malformed contours outright — never silently truncate.
  if (f.contour.length > MAX_FILL_CONTOUR_VALUES) return null
  const contour: number[] = []
  for (const n of f.contour) {
    if (typeof n !== 'number' || !Number.isFinite(n)) return null
    if (n < CONTOUR_COORD_MIN || n > CONTOUR_COORD_MAX) return null
    contour.push(n)
  }
  if (contour.length < 6 || contour.length % 2 !== 0) return null
  const style = parseFillStyle(f.style)
  if (!style) return null
  const seedX = typeof f.seedX === 'number' && Number.isFinite(f.seedX) ? f.seedX : contour[0]!
  const seedY = typeof f.seedY === 'number' && Number.isFinite(f.seedY) ? f.seedY : contour[1]!
  const eraseAfterStrokeIndex =
    typeof f.eraseAfterStrokeIndex === 'number' &&
    Number.isFinite(f.eraseAfterStrokeIndex) &&
    f.eraseAfterStrokeIndex >= 0
      ? Math.floor(f.eraseAfterStrokeIndex)
      : undefined
  return {
    id: typeof f.id === 'string' && f.id ? f.id : createFillId(),
    contour,
    style,
    seedX,
    seedY,
    ...(eraseAfterStrokeIndex !== undefined ? { eraseAfterStrokeIndex } : {}),
  }
}

export type PersistableFillResult =
  | { ok: true; fill: FillOp }
  | { ok: false; message: string }

/**
 * Ensure a newly generated fill can round-trip through saved-design parse bounds
 * before it enters editor state. Never silently truncate contours.
 */
export function checkPersistableFill(fill: FillOp): PersistableFillResult {
  const parsed = parseFillOp(fill)
  if (parsed) return { ok: true, fill: parsed }

  if (!Array.isArray(fill.contour) || fill.contour.length < 6 || fill.contour.length % 2 !== 0) {
    return {
      ok: false,
      message: 'That fill outline is too small to keep. Try tapping inside a larger closed area.',
    }
  }
  if (fill.contour.length > MAX_FILL_CONTOUR_VALUES) {
    return {
      ok: false,
      message:
        'That fill outline is too detailed to save. Try a simpler closed region — nothing was added.',
    }
  }
  for (const n of fill.contour) {
    if (typeof n !== 'number' || !Number.isFinite(n) || n < CONTOUR_COORD_MIN || n > CONTOUR_COORD_MAX) {
      return {
        ok: false,
        message:
          'That fill could not be saved in a form that reopens correctly. Nothing was added.',
      }
    }
  }
  return {
    ok: false,
    message: 'That fill could not be saved in a form that reopens correctly. Nothing was added.',
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
    s.gradientId.length > 0 &&
    s.gradientId.length <= 64 &&
    Array.isArray(s.colors) &&
    s.colors.length >= 2 &&
    typeof s.colors[0] === 'string' &&
    typeof s.colors[1] === 'string'
  ) {
    const c0 = String(s.colors[0]).toUpperCase()
    const c1 = String(s.colors[1]).toUpperCase()
    // Historical gradients may use any stored HEX; keep them when parseable.
    if (!/^#[0-9A-F]{6}$/.test(c0) || !/^#[0-9A-F]{6}$/.test(c1)) return null
    return {
      kind: 'gradient',
      gradientId: s.gradientId,
      colors: [c0, c1],
      angle: normalizeGradientAngle(typeof s.angle === 'number' ? s.angle : 135),
    }
  }
  if (s.kind === 'fabric' && typeof s.fabricId === 'string') {
    const known = FABRIC_PRESETS.some((p) => p.id === s.fabricId)
    if (!known) return null
    return { kind: 'fabric', fabricId: s.fabricId }
  }
  if (s.kind === 'uploaded-fabric' && typeof s.assetId === 'string' && isAssetId(s.assetId)) {
    return {
      kind: 'uploaded-fabric',
      assetId: s.assetId.toLowerCase(),
      scale: clampUploadedFabricScale(typeof s.scale === 'number' ? s.scale : UPLOADED_FABRIC_SCALE_DEFAULT),
    }
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

export function uploadedFabricStyle(
  assetId: string,
  scale: number = UPLOADED_FABRIC_SCALE_DEFAULT,
): UploadedFabricFillStyle | null {
  if (!isAssetId(assetId)) return null
  return {
    kind: 'uploaded-fabric',
    assetId: assetId.toLowerCase(),
    scale: clampUploadedFabricScale(scale),
  }
}

/** Asset ids referenced by uploaded-fabric fills (deduped). */
export function collectUploadedFabricAssetIds(fills: FillOp[]): string[] {
  const ids: string[] = []
  const seen = new Set<string>()
  for (const fill of fills) {
    if (fill.style.kind !== 'uploaded-fabric') continue
    const id = fill.style.assetId
    if (seen.has(id)) continue
    seen.add(id)
    ids.push(id)
  }
  return ids
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

/** Original four presets must keep stable ids/values forever. */
export const LEGACY_GRADIENT_IDS = [
  'rose-violet',
  'champagne',
  'ocean-blush',
  'noir-wine',
] as const
