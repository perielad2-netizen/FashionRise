import type {
  MeasuredValue,
  MeasuredValueSource,
  TechpackPiece,
  TechpackPieceCategory,
  TechpackSpecV2,
} from '@/services/techpacksApi'
import { FINISHED_POM_BY_CATEGORY, PIECE_CATEGORIES, POM_LABELS } from './fieldHelpContent'

const MEASURED_SOURCES: MeasuredValueSource[] = [
  'empty',
  'designer',
  'estimate',
  'ai',
  'look',
  'calculated',
  'unknown',
]

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function measured(raw: unknown, unitFallback = 'cm'): MeasuredValue {
  const row = asRecord(raw)
  const source = typeof row.source === 'string' ? row.source : 'empty'
  return {
    value: (row.value as number | string | null | undefined) ?? null,
    unit: typeof row.unit === 'string' ? row.unit : unitFallback,
    source: MEASURED_SOURCES.includes(source as MeasuredValueSource)
      ? (source as MeasuredValueSource)
      : 'empty',
    note: typeof row.note === 'string' ? row.note : null,
    definition: typeof row.definition === 'string' ? row.definition : null,
    confidence: typeof row.confidence === 'string' ? row.confidence : null,
    review_status: typeof row.review_status === 'string' ? row.review_status : null,
    assumptions: Array.isArray(row.assumptions)
      ? row.assumptions.filter((x): x is string => typeof x === 'string')
      : undefined,
  }
}

export function emptyFinishedMeasurements(
  category: string,
  units = 'cm',
): Record<string, MeasuredValue> {
  const keys = FINISHED_POM_BY_CATEGORY[category] ?? FINISHED_POM_BY_CATEGORY.other
  const out: Record<string, MeasuredValue> = {}
  for (const key of keys) {
    out[key] = {
      value: null,
      unit: units,
      source: 'empty',
      definition: POM_LABELS[key] ?? key,
      confidence: 'unknown',
      review_status: 'open',
      assumptions: [],
    }
  }
  return out
}

export function createEmptyPiece(
  opts: {
    id?: string
    category?: TechpackPieceCategory | string
    label?: string
    color_hint?: string
    units?: string
  } = {},
): TechpackPiece {
  const category = (opts.category && PIECE_CATEGORIES.includes(opts.category as (typeof PIECE_CATEGORIES)[number])
    ? opts.category
    : 'other') as TechpackPieceCategory
  const id = opts.id ?? `piece-${Math.random().toString(36).slice(2, 10)}`
  return {
    id,
    category,
    label: opts.label ?? `${category[0].toUpperCase()}${category.slice(1)}`,
    role: category,
    color_hint: opts.color_hint ?? '',
    detection_source: 'user',
    materials: {
      shell: { name: '', suggestion: '', composition: '', source: 'empty' },
      lining: { name: '', source: 'empty' },
      interfacing: { name: '', source: 'empty' },
    },
    closures: { type: '', suggestion: '', notes: '', source: 'empty' },
    fit: { silhouette: '', suggestion: '', ease_note: '' },
    finished_measurements: emptyFinishedMeasurements(category, opts.units ?? 'cm'),
    bom: [],
    pattern_pieces: [],
    construction_steps: [],
    illustrations: {
      flat_front: 'schematic_pending',
      flat_back: 'schematic_pending',
      cutting: 'schematic_pending',
      label: 'PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE',
    },
  }
}

export function isV2Spec(spec: Record<string, unknown>): boolean {
  const outfit = asRecord(spec.outfit)
  return (
    String(spec.schema_version || '').startsWith('2') ||
    (Array.isArray(outfit.pieces) && outfit.pieces.length > 0)
  )
}

/** Locally wrap a V1 flat spec into a single editable piece without claiming BE migration yet. */
export function wrapSpecForEditing(raw: Record<string, unknown>): {
  spec: TechpackSpecV2
  wasV1: boolean
} {
  if (isV2Spec(raw)) {
    const outfit = asRecord(raw.outfit)
    const pieces = (Array.isArray(outfit.pieces) ? outfit.pieces : [])
      .filter((p): p is Record<string, unknown> => Boolean(p) && typeof p === 'object')
      .map((p, idx) => normalizePiece(p, idx, String(raw.units || 'cm')))
    return {
      wasV1: false,
      spec: {
        ...raw,
        schema_version: String(raw.schema_version || '2.0'),
        workflow_stage: String(raw.workflow_stage || 'understand'),
        units: String(raw.units || 'cm'),
        size_system: String(raw.size_system || 'EU'),
        sample_size: String(raw.sample_size || ''),
        look_notes: typeof raw.look_notes === 'string' ? raw.look_notes : '',
        designer_notes: typeof raw.designer_notes === 'string' ? raw.designer_notes : '',
        outfit: {
          piece_count: pieces.length,
          pieces,
          detection_confidence:
            typeof outfit.detection_confidence === 'string' ? outfit.detection_confidence : undefined,
          needs_user_confirm: Boolean(outfit.needs_user_confirm),
          note: typeof outfit.note === 'string' ? outfit.note : undefined,
        },
        body: normalizeBody(asRecord(raw.body), String(raw.units || 'cm')),
        preferences: {
          fit_preference: String(asRecord(raw.preferences).fit_preference || 'regular'),
          notes: String(asRecord(raw.preferences).notes || ''),
        },
        warnings: Array.isArray(raw.warnings) ? (raw.warnings as TechpackSpecV2['warnings']) : [],
        qc_checklist: Array.isArray(raw.qc_checklist)
          ? (raw.qc_checklist as TechpackSpecV2['qc_checklist'])
          : undefined,
        ai: asRecord(raw.ai) as TechpackSpecV2['ai'],
      },
    }
  }

  const units = String(raw.units || 'cm')
  const materials = asRecord(raw.materials)
  const shell = asRecord(materials.shell)
  const closures = asRecord(raw.closures)
  const fit = asRecord(raw.fit)
  const garment = asRecord(raw.garment)
  const piece = createEmptyPiece({
    id: 'piece-1',
    category: 'dress',
    label: typeof shell.name === 'string' && shell.name ? String(shell.name) : 'Garment',
    units,
  })
  piece.detection_source = 'migrated_v1_local'
  piece.materials = {
    shell: {
      name: typeof shell.name === 'string' ? shell.name : '',
      composition: typeof shell.composition === 'string' ? shell.composition : '',
      suggestion: '',
      source: typeof shell.source === 'string' ? shell.source : shell.name ? 'designer' : 'empty',
    },
    lining: { name: '', source: 'empty' },
    interfacing: { name: '', source: 'empty' },
  }
  piece.closures = {
    type: typeof closures.type === 'string' ? closures.type : '',
    suggestion: '',
    notes: typeof closures.notes === 'string' ? closures.notes : '',
    source: typeof closures.source === 'string' ? closures.source : 'empty',
  }
  piece.fit = {
    silhouette: typeof fit.silhouette === 'string' ? fit.silhouette : '',
    suggestion: '',
    ease_note: '',
  }
  const legacyMap: Record<string, string> = {
    garment_length: 'garment_length',
    shoulder_width: 'shoulder_width',
    sleeve_length: 'sleeve_length',
    inseam: 'inseam',
  }
  for (const [legacy, target] of Object.entries(legacyMap)) {
    if (piece.finished_measurements?.[target] && garment[legacy]) {
      piece.finished_measurements[target] = {
        ...piece.finished_measurements[target],
        ...measured(garment[legacy], units),
        definition: POM_LABELS[target],
      }
    }
  }

  return {
    wasV1: true,
    spec: {
      schema_version: '2.0',
      workflow_stage: 'understand',
      units,
      size_system: String(raw.size_system || 'EU'),
      sample_size: String(raw.sample_size || ''),
      look_notes: typeof raw.look_notes === 'string' ? raw.look_notes : '',
      designer_notes: typeof raw.designer_notes === 'string' ? raw.designer_notes : '',
      outfit: {
        piece_count: 1,
        pieces: [piece],
        detection_confidence: 'migrated',
        needs_user_confirm: true,
        note: 'Loaded as a single piece from an older draft. Saving will migrate on the server.',
      },
      body: normalizeBody(asRecord(raw.body), units),
      preferences: {
        fit_preference: typeof fit.silhouette === 'string' && fit.silhouette ? fit.silhouette : 'regular',
        notes: '',
      },
      warnings: [],
      ai: { last_run_id: null, paid_sections: [] },
    },
  }
}

function normalizeBody(body: Record<string, unknown>, units: string): Record<string, MeasuredValue> {
  const keys = ['height', 'bust', 'waist', 'hip', 'inseam'] as const
  const out: Record<string, MeasuredValue> = {}
  for (const key of keys) {
    out[key] = measured(body[key], units)
  }
  return out
}

function normalizePiece(raw: Record<string, unknown>, idx: number, units: string): TechpackPiece {
  const category = String(raw.category || 'other')
  const base = createEmptyPiece({
    id: typeof raw.id === 'string' && raw.id ? raw.id : `piece-${idx + 1}`,
    category,
    label: typeof raw.label === 'string' && raw.label ? raw.label : `Piece ${idx + 1}`,
    color_hint: typeof raw.color_hint === 'string' ? raw.color_hint : '',
    units,
  })
  const materials = asRecord(raw.materials)
  const shell = asRecord(materials.shell)
  const closures = asRecord(raw.closures)
  const fit = asRecord(raw.fit)
  const finishedRaw = asRecord(raw.finished_measurements)
  const finished: Record<string, MeasuredValue> = { ...base.finished_measurements }
  // Prefer keys already present on the piece (garment-specific).
  const keys =
    Object.keys(finishedRaw).length > 0
      ? Object.keys(finishedRaw)
      : Object.keys(finished)
  const nextFinished: Record<string, MeasuredValue> = {}
  for (const key of keys) {
    nextFinished[key] = {
      ...(finished[key] ?? emptyFinishedMeasurements(category, units)[key] ?? measured(null, units)),
      ...measured(finishedRaw[key] ?? finished[key], units),
      definition: POM_LABELS[key] ?? key,
    }
  }
  return {
    ...base,
    ...raw,
    id: base.id,
    category,
    label: base.label,
    color_hint: base.color_hint,
    materials: {
      shell: {
        name: typeof shell.name === 'string' ? shell.name : '',
        composition: typeof shell.composition === 'string' ? shell.composition : '',
        suggestion: typeof shell.suggestion === 'string' ? shell.suggestion : '',
        source: typeof shell.source === 'string' ? shell.source : 'empty',
      },
      lining: {
        name: typeof asRecord(materials.lining).name === 'string' ? String(asRecord(materials.lining).name) : '',
        source:
          typeof asRecord(materials.lining).source === 'string'
            ? String(asRecord(materials.lining).source)
            : 'empty',
      },
      interfacing: {
        name:
          typeof asRecord(materials.interfacing).name === 'string'
            ? String(asRecord(materials.interfacing).name)
            : '',
        source:
          typeof asRecord(materials.interfacing).source === 'string'
            ? String(asRecord(materials.interfacing).source)
            : 'empty',
      },
    },
    closures: {
      type: typeof closures.type === 'string' ? closures.type : '',
      suggestion: typeof closures.suggestion === 'string' ? closures.suggestion : '',
      notes: typeof closures.notes === 'string' ? closures.notes : '',
      source: typeof closures.source === 'string' ? closures.source : 'empty',
    },
    fit: {
      silhouette: typeof fit.silhouette === 'string' ? fit.silhouette : '',
      suggestion: typeof fit.suggestion === 'string' ? fit.suggestion : '',
      ease_note: typeof fit.ease_note === 'string' ? fit.ease_note : '',
    },
    finished_measurements: nextFinished,
  }
}

export function pieceTabLabel(piece: TechpackPiece): string {
  const cat = String(piece.category || 'piece').toUpperCase()
  const label = String(piece.label || '').trim().toUpperCase()
  return label ? `${cat} — ${label}` : cat
}

export function retargetFinishedMeasurements(
  piece: TechpackPiece,
  nextCategory: string,
  units = 'cm',
): TechpackPiece {
  const prev = piece.finished_measurements ?? {}
  const nextKeys = FINISHED_POM_BY_CATEGORY[nextCategory] ?? FINISHED_POM_BY_CATEGORY.other
  const next: Record<string, MeasuredValue> = {}
  for (const key of nextKeys) {
    next[key] = prev[key]
      ? { ...prev[key], definition: POM_LABELS[key] ?? key }
      : {
          value: null,
          unit: units,
          source: 'empty',
          definition: POM_LABELS[key] ?? key,
          confidence: 'unknown',
          review_status: 'open',
          assumptions: [],
        }
  }
  return {
    ...piece,
    category: nextCategory,
    finished_measurements: next,
  }
}
