import { describe, expect, it } from 'vitest'
import { rearUnavailableReasonForModel } from '@/shell/rearUnavailableReason'
import { modelHasRearAsset } from '@/assets/modelLibrary'
import { referenceUrlForModelSide } from '@/hooks/studioEditorSides'

describe('personal croquis front-only', () => {
  it('has no rear asset and explains Front-only behavior', () => {
    expect(modelHasRearAsset('personal')).toBe(false)
    expect(rearUnavailableReasonForModel('personal')).toMatch(/front-only/i)
  })

  it('never invents a back underlay URL for personal', () => {
    expect(referenceUrlForModelSide('personal', 'back', null, 'blob:front')).toBeNull()
    expect(referenceUrlForModelSide('personal', 'front', null, 'blob:front')).toBe('blob:front')
    expect(referenceUrlForModelSide('personal', 'front', null, null)).toBeNull()
  })
})
