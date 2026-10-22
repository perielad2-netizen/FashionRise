/**
 * WEB-V4D built-in croquis library.
 *
 * Canvas assets: `/models/library/<id>.png`
 * Card thumbs: `/assets/ui/models/library/<id>_card.png`
 *
 * Legacy draft values `female` / `male` remain the selectable IDs for the
 * standing-straight defaults so existing cloud drafts keep working.
 */

export type ModelGender = 'female' | 'male'

/** Selectable built-in croquis + utility modes. */
export type BuiltinModelId =
  | 'female'
  | 'female-hand-hip'
  | 'female-contrapposto'
  | 'female-cross-ankle'
  | 'female-atelier'
  | 'female-cross-leg'
  | 'male'
  | 'male-step'
  | 'male-walk'
  | 'male-contrapposto'

export type UtilityModelId = 'custom' | 'blank'

export type ModelChoice = BuiltinModelId | UtilityModelId

export type BuiltinModelDef = {
  id: BuiltinModelId
  gender: ModelGender
  label: string
  /** Short subtitle under the card. */
  pose: string
  canvasSrc: string
  cardSrc: string
  /** Default selection when switching into this gender filter. */
  defaultForGender: boolean
}

export const BUILTIN_MODELS: readonly BuiltinModelDef[] = [
  {
    id: 'female',
    gender: 'female',
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
    id: 'male',
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

const BY_ID = new Map(BUILTIN_MODELS.map((m) => [m.id, m]))

export const DEFAULT_FEMALE_MODEL: BuiltinModelId = 'female'
export const DEFAULT_MALE_MODEL: BuiltinModelId = 'male'
export const DEFAULT_MODEL: ModelChoice = DEFAULT_FEMALE_MODEL

export const MODEL_CHOICES: readonly ModelChoice[] = [
  ...BUILTIN_MODELS.map((m) => m.id),
  'custom',
  'blank',
]

export function isModelChoice(value: unknown): value is ModelChoice {
  return typeof value === 'string' && (MODEL_CHOICES as readonly string[]).includes(value)
}

/** Map unknown / legacy aliases onto a safe selectable model. */
export function normalizeModelChoice(value: unknown): ModelChoice {
  if (isModelChoice(value)) return value
  // Older exploratory ids if any appear in local recovery.
  if (value === 'female-straight') return 'female'
  if (value === 'male-straight') return 'male'
  return DEFAULT_MODEL
}

export function getBuiltinModel(id: ModelChoice): BuiltinModelDef | null {
  if (id === 'custom' || id === 'blank') return null
  return BY_ID.get(id) ?? null
}

export function canvasSrcForModel(id: ModelChoice): string | null {
  if (id === 'custom' || id === 'blank') return null
  return BY_ID.get(id)?.canvasSrc ?? null
}

export function defaultModelForGender(gender: ModelGender): BuiltinModelId {
  return gender === 'male' ? DEFAULT_MALE_MODEL : DEFAULT_FEMALE_MODEL
}

export function modelLabel(model: ModelChoice): string {
  if (model === 'custom') return 'Custom reference'
  if (model === 'blank') return 'Blank paper'
  const def = BY_ID.get(model)
  if (!def) return 'Studio model'
  return `${def.label} · ${def.pose}`
}
