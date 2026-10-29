import { describe, expect, it } from 'vitest'
import type { TechpackSpecV2 } from '@/services/techpacksApi'
import {
  buildEditorPersistSnapshot,
  editorPersistFingerprint,
} from '@/shell/components/techpack/editorPersistSnapshot'

const SPEC: TechpackSpecV2 = {
  schema_version: '2.0',
  workflow_stage: 'understand',
  units: 'cm',
  size_system: 'EU',
  sample_size: '',
  look_notes: 'notes',
  designer_notes: '',
  outfit: { piece_count: 0, pieces: [] },
  body: { height: { value: 170, unit: 'cm', source: 'designer' } },
  preferences: { fit_preference: 'regular', notes: '' },
  warnings: [],
  ai: {
    last_run_id: 'run-1',
    last_mode: 'professional',
    export_id: 'exp-1',
    dirty_since_generation: false,
  },
}

describe('editorPersistFingerprint', () => {
  it('is stable for equal editable values despite object identity / workflow_stage', () => {
    const a = editorPersistFingerprint('  Title  ', ' FR ', SPEC)
    const b = editorPersistFingerprint('Title', 'FR', { ...SPEC, workflow_stage: 'generate' })
    expect(a).toBe(b)
  })

  it('changes when a measurement value changes', () => {
    const before = editorPersistFingerprint('Title', 'FR', SPEC)
    const after = editorPersistFingerprint('Title', 'FR', {
      ...SPEC,
      body: { height: { value: 171, unit: 'cm', source: 'designer' } },
    })
    expect(after).not.toBe(before)
  })

  it('ignores server-owned ai metadata changes (dirty_since_generation / export_id)', () => {
    const before = editorPersistFingerprint('Title', 'FR', SPEC)
    const after = editorPersistFingerprint('Title', 'FR', {
      ...SPEC,
      ai: {
        ...SPEC.ai,
        dirty_since_generation: true,
        export_id: 'exp-2',
        last_run_id: 'run-2',
      },
    })
    expect(after).toBe(before)
  })

  it('buildEditorPersistSnapshot still includes ai for PATCH merge compatibility', () => {
    const snap = buildEditorPersistSnapshot('  X ', ' Y ', SPEC)
    expect(snap).toEqual({
      title: 'X',
      style_code: 'Y',
      spec: expect.objectContaining({
        workflow_stage: 'generate',
        look_notes: 'notes',
        ai: expect.objectContaining({ last_run_id: 'run-1', dirty_since_generation: false }),
      }),
    })
  })
})
