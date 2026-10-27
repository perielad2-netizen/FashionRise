import type { TechpackSpecV2 } from '@/services/techpacksApi'

/**
 * Canonical editable payload for PATCH bodies.
 * Must match what TechpackScreen sends in updateTechpackDraft.
 */
export function buildEditorSpecPatch(spec: TechpackSpecV2 | null | undefined): TechpackSpecV2 {
  const current = spec ?? {
    schema_version: '2.0',
    units: 'cm',
    size_system: 'EU',
    sample_size: '',
    look_notes: '',
    designer_notes: '',
    outfit: { piece_count: 0, pieces: [] },
    body: {},
    preferences: { fit_preference: 'regular', notes: '' },
    warnings: [],
  }
  return {
    ...current,
    schema_version: '2.0',
    workflow_stage: 'generate',
    designer_notes: current.designer_notes ?? '',
    look_notes: current.look_notes ?? '',
    units: current.units || 'cm',
    size_system: current.size_system || 'EU',
    sample_size: current.sample_size || '',
    outfit: {
      piece_count: current.outfit?.pieces?.length ?? 0,
      pieces: current.outfit?.pieces ?? [],
      detection_confidence: current.outfit?.detection_confidence,
      needs_user_confirm: current.outfit?.needs_user_confirm,
      note: current.outfit?.note,
    },
    body: current.body ?? {},
    preferences: current.preferences ?? { fit_preference: 'regular', notes: '' },
    warnings: current.warnings ?? [],
    qc_checklist: current.qc_checklist,
    // Included in PATCH for merge compatibility; excluded from dirty fingerprint below.
    ai: current.ai,
  }
}

export type EditorPersistSnapshot = {
  title: string
  style_code: string
  spec: TechpackSpecV2
}

export function buildEditorPersistSnapshot(
  title: string,
  styleCode: string,
  spec: TechpackSpecV2 | null | undefined,
): EditorPersistSnapshot {
  return {
    title: title.trim(),
    style_code: styleCode.trim(),
    spec: buildEditorSpecPatch(spec),
  }
}

/**
 * Value fingerprint for quiet autosave dirty checks.
 * Omits server-owned `ai` metadata (dirty_since_generation, last_run_id, export_id, …)
 * so syncing PDF validity after PATCH cannot re-arm the autosave loop.
 */
export function editorPersistFingerprint(
  title: string,
  styleCode: string,
  spec: TechpackSpecV2 | null | undefined,
): string {
  const snap = buildEditorPersistSnapshot(title, styleCode, spec)
  const { ai: _serverOwnedAi, ...editableSpec } = snap.spec
  return JSON.stringify({
    title: snap.title,
    style_code: snap.style_code,
    spec: editableSpec,
  })
}
