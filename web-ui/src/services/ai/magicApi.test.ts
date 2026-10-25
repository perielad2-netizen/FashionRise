import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  BUILTIN_MODELS,
  type ModelChoice,
  type SelectableBuiltinModelId,
} from '@/assets/modelLibrary'

const apiRequest = vi.fn()

vi.mock('@/services/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/client')>(
    '@/services/api/client',
  )
  return { ...actual, apiRequest: (...args: unknown[]) => apiRequest(...args) }
})

import { enqueueSketchPolish } from '@/services/ai/magicApi'

const ALL_SELECTABLE_IDS = BUILTIN_MODELS.map((m) => m.id)
const MALE_IDS = ALL_SELECTABLE_IDS.filter((id) => id.startsWith('male-'))
const FEMALE_IDS = ALL_SELECTABLE_IDS.filter((id) => id.startsWith('female-'))

describe('enqueueSketchPolish reference_model_id contract', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiRequest.mockResolvedValue({
      id: 'job-1',
      user_id: 'u1',
      design_id: null,
      job_type: 'sketch_polish',
      status: 'queued',
      input_data: {},
      result_data: null,
      error_message: null,
      created_at: '2026-10-25T00:00:00Z',
      updated_at: '2026-10-25T00:00:00Z',
    })
  })

  it.each([...MALE_IDS, 'male'] as ModelChoice[])(
    'sends male library/legacy id %s as reference_model_id',
    async (modelId) => {
      await enqueueSketchPolish({
        imageBase64: 'data:image/png;base64,AAA',
        referenceModelId: modelId,
        notes: 'polish concept',
      })
      expect(apiRequest).toHaveBeenCalledTimes(1)
      const [path, options] = apiRequest.mock.calls[0]!
      expect(path).toBe('/ai/sketch/polish')
      expect(options).toMatchObject({
        method: 'POST',
        body: {
          design_id: null,
          input_data: {
            notes: 'polish concept',
            image_base64: 'data:image/png;base64,AAA',
            reference_model_id: modelId,
          },
        },
      })
    },
  )

  it.each([...FEMALE_IDS, 'female'] as ModelChoice[])(
    'sends female library/legacy id %s as reference_model_id',
    async (modelId) => {
      await enqueueSketchPolish({
        imageBase64: 'data:image/png;base64,AAA',
        referenceModelId: modelId,
      })
      const [, options] = apiRequest.mock.calls[0]!
      expect(options.body.input_data.reference_model_id).toBe(modelId)
    },
  )

  it.each(['custom', 'blank'] as ModelChoice[])(
    'sends utility id %s without inventing gender metadata',
    async (modelId) => {
      await enqueueSketchPolish({
        imageBase64: 'data:image/png;base64,AAA',
        referenceModelId: modelId,
      })
      const [, options] = apiRequest.mock.calls[0]!
      expect(options.body.input_data.reference_model_id).toBe(modelId)
      expect(options.body.input_data).not.toHaveProperty('gender')
      expect(options.body.input_data).not.toHaveProperty('croquis_family')
    },
  )

  it('snapshots the caller-supplied model id (mid-flight switch safety)', async () => {
    // Mirrors useStudioEditor: capture `model` into a local before async sketch work.
    let selected: ModelChoice = 'male-straight'
    const referenceModelId = selected
    selected = 'female-straight'
    await enqueueSketchPolish({
      imageBase64: 'data:image/png;base64,AAA',
      referenceModelId,
    })
    const [, options] = apiRequest.mock.calls[0]!
    expect(options.body.input_data.reference_model_id).toBe('male-straight')
    expect(selected).toBe('female-straight')
  })

  it('covers all ten selectable builtins in the FE→BE contract', () => {
    const ids = new Set<SelectableBuiltinModelId>(ALL_SELECTABLE_IDS)
    expect(ids.size).toBe(10)
    expect(MALE_IDS).toHaveLength(4)
    expect(FEMALE_IDS).toHaveLength(6)
  })
})
