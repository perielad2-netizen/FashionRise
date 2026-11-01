import { describe, expect, it, vi } from 'vitest'
import { rearUnavailableReasonForModel } from '@/shell/rearUnavailableReason'
import { modelHasRearAsset } from '@/assets/modelLibrary'

describe('personal croquis front-only underlay, accessible Back ink', () => {
  it('has no rear croquis image but may open Back paper when Front/Back is ON', async () => {
    expect(modelHasRearAsset('personal')).toBe(false)
    expect(rearUnavailableReasonForModel('personal')).toMatch(/front-only/i)
    vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
    vi.resetModules()
    const { canOpenBackPaper, rearReferenceAvailable, referenceUrlForModelSide } = await import(
      '@/hooks/studioEditorSides'
    )
    expect(rearReferenceAvailable('personal')).toBe(false)
    expect(canOpenBackPaper('personal')).toBe(true)
    expect(referenceUrlForModelSide('personal', 'back', null, 'blob:front')).toBeNull()
    expect(referenceUrlForModelSide('personal', 'front', null, 'blob:front')).toBe('blob:front')
  })
})
