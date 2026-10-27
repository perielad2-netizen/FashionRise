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

  it('buildEditorPersistSnapshot trims title/style and normalizes stage', () => {
    const snap = buildEditorPersistSnapshot('  X ', ' Y ', SPEC)
    expect(snap).toEqual({
      title: 'X',
      style_code: 'Y',
      spec: expect.objectContaining({ workflow_stage: 'generate', look_notes: 'notes' }),
    })
  })
})
