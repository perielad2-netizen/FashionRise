import { isRearCroquisPublished } from '@/assets/rearCroquisPublished'

/**
 * WEB-V4D built-in croquis library.
 *
 * Canvas assets (new): `/models/library/<id>.png`
 * Card thumbs (new): `/assets/ui/models/library/<id>_card.png`
 *
 * Legacy draft/saved IDs `female` / `male` resolve to the ORIGINAL croquis
 * geometry under `/models/female_model.png` and `/models/male_model_display.png`.
 * They remain valid ModelChoice values so old artwork is never remapped onto a
 * different figure. They are NOT offered in the new model picker.
 *
 * New drawings default to `female-straight` / `male-straight`.
 */

export type ModelGender = 'female' | 'male'

/** Legacy IDs persisted by pre-V4D drafts and saved designs. */
export type LegacyModelId = 'female' | 'male'

/** Selectable built-in croquis in the V4D picker (10 = 6F + 4M). */
export type SelectableBuiltinModelId =
  | 'female-straight'
  | 'female-hand-hip'
  | 'female-contrapposto'
  | 'female-cross-ankle'
  | 'female-atelier'
  | 'female-cross-leg'
  | 'male-straight'
  | 'male-step'
  | 'male-walk'
  | 'male-contrapposto'

export type BuiltinModelId = LegacyModelId | SelectableBuiltinModelId

export type UtilityModelId = 'custom' | 'blank'

export type ModelChoice = BuiltinModelId | UtilityModelId

export type BuiltinModelDef = {
  id: SelectableBuiltinModelId
  gender: ModelGender
  label: string
  /** Short subtitle under the card. */
  pose: string
  canvasSrc: string
  /** Rear croquis when published (`/models/library/<id>-back.png`). */
  backCanvasSrc?: string
  cardSrc: string
  /** Default selection when switching into this gender filter. */
  defaultForGender: boolean
}

export type ModelCanvasSide = 'front' | 'back'

function libraryBackSrc(id: SelectableBuiltinModelId): string {
  return `/models/library/${id}-back.png`
}

/** Original pre-V4D canvas references — keep forever for reopen fidelity. */
export const LEGACY_MODEL_CANVAS: Readonly<Record<LegacyModelId, string>> = {
  female: '/models/female_model.png',
  male: '/models/male_model_display.png',
}

const BUILTIN_MODELS_BASE = [
  {
    id: 'female-straight' as const,
    gender: 'female' as const,
    label: 'Female',
    pose: 'Standing',
    canvasSrc: '/models/library/female-straight.png',
    cardSrc: '/assets/ui/models/library/female-straight_card.png',
    defaultForGender: true,
  },
  {
    id: 'female-hand-hip',
    gender: 'female',
    label: 'Female',
    pose: 'Hand on hip',
    canvasSrc: '/models/library/female-hand-hip.png',
    cardSrc: '/assets/ui/models/library/female-hand-hip_card.png',
    defaultForGender: false,
  },
  {
    id: 'female-contrapposto',
    gender: 'female',
    label: 'Female',
    pose: 'Contrapposto',
    canvasSrc: '/models/library/female-contrapposto.png',
    cardSrc: '/assets/ui/models/library/female-contrapposto_card.png',
    defaultForGender: false,
  },
  {
    id: 'female-cross-ankle',
    gender: 'female',
    label: 'Female',
    pose: 'Crossed ankles',
    canvasSrc: '/models/library/female-cross-ankle.png',
    cardSrc: '/assets/ui/models/library/female-cross-ankle_card.png',
    defaultForGender: false,
  },
  {
    id: 'female-atelier',
    gender: 'female',
    label: 'Female',
    pose: 'Atelier',
    canvasSrc: '/models/library/female-atelier.png',
    cardSrc: '/assets/ui/models/library/female-atelier_card.png',
    defaultForGender: false,
  },
  {
    id: 'female-cross-leg',
    gender: 'female',
    label: 'Female',
    pose: 'Crossed leg',
    canvasSrc: '/models/library/female-cross-leg.png',
    cardSrc: '/assets/ui/models/library/female-cross-leg_card.png',
    defaultForGender: false,
  },
  {
    id: 'male-straight',
    gender: 'male',
    label: 'Male',
    pose: 'Standing',
    canvasSrc: '/models/library/male-straight.png',
    cardSrc: '/assets/ui/models/library/male-straight_card.png',
    defaultForGender: true,
  },
  {
    id: 'male-step',
    gender: 'male',
    label: 'Male',
    pose: 'Step',
    canvasSrc: '/models/library/male-step.png',
    cardSrc: '/assets/ui/models/library/male-step_card.png',
    defaultForGender: false,
  },
  {
    id: 'male-walk',
    gender: 'male',
    label: 'Male',
    pose: 'Walk',
    canvasSrc: '/models/library/male-walk.png',
    cardSrc: '/assets/ui/models/library/male-walk_card.png',
    defaultForGender: false,
  },
  {
    id: 'male-contrapposto',
    gender: 'male',
    label: 'Male',
    pose: 'Contrapposto',
    canvasSrc: '/models/library/male-contrapposto.png',
    cardSrc: '/assets/ui/models/library/male-contrapposto_card.png',
    defaultForGender: false,
  },
] as const

export const BUILTIN_MODELS: readonly BuiltinModelDef[] = BUILTIN_MODELS_BASE.map((m) => ({
  ...m,
  backCanvasSrc: libraryBackSrc(m.id),
}))

const SELECTABLE_BY_ID = new Map(BUILTIN_MODELS.map((m) => [m.id, m]))

export const DEFAULT_FEMALE_MODEL: SelectableBuiltinModelId = 'female-straight'
export const DEFAULT_MALE_MODEL: SelectableBuiltinModelId = 'male-straight'
export const DEFAULT_MODEL: ModelChoice = DEFAULT_FEMALE_MODEL

export const MODEL_CHOICES: readonly ModelChoice[] = [
  'female',
  'male',
  ...BUILTIN_MODELS.map((m) => m.id),
  'custom',
  'blank',
]

export function isLegacyModelId(value: unknown): value is LegacyModelId {
  return value === 'female' || value === 'male'
}

export function isModelChoice(value: unknown): value is ModelChoice {
  return typeof value === 'string' && (MODEL_CHOICES as readonly string[]).includes(value)
}

/**
 * Parse stored model ids without rewriting legacy geometry.
 * Unknown values fall back to the NEW default (female-straight).
 */
export function normalizeModelChoice(value: unknown): ModelChoice {
  if (isModelChoice(value)) return value
  return DEFAULT_MODEL
}

export function getBuiltinModel(id: ModelChoice): BuiltinModelDef | null {
  if (id === 'custom' || id === 'blank' || isLegacyModelId(id)) return null
  return SELECTABLE_BY_ID.get(id) ?? null
}

/** Resolve the exact canvas URL for a stored model choice and paper side. */
export function canvasSrcForModel(id: ModelChoice, side: ModelCanvasSide = 'front'): string | null {
  if (id === 'custom' || id === 'blank') return null
  if (isLegacyModelId(id)) return side === 'back' ? null : LEGACY_MODEL_CANVAS[id]
  const def = SELECTABLE_BY_ID.get(id)
  if (!def) return null
  if (side === 'back') return def.backCanvasSrc ?? libraryBackSrc(def.id)
  return def.canvasSrc
}

export function modelHasRearAsset(id: ModelChoice): boolean {
  if (id === 'custom' || id === 'blank' || isLegacyModelId(id)) return false
  const def = SELECTABLE_BY_ID.get(id)
  if (!def) return false
  return isRearCroquisPublished(def.id)
}

export function defaultModelForGender(gender: ModelGender): SelectableBuiltinModelId {
  return gender === 'male' ? DEFAULT_MALE_MODEL : DEFAULT_FEMALE_MODEL
}

export function modelLabel(model: ModelChoice): string {
  if (model === 'custom') return 'Custom reference'
  if (model === 'blank') return 'Blank paper'
  if (model === 'female') return 'Female · Classic'
  if (model === 'male') return 'Male · Classic'
  const def = SELECTABLE_BY_ID.get(model)
  if (!def) return 'Studio model'
  return `${def.label} · ${def.pose}`
}
