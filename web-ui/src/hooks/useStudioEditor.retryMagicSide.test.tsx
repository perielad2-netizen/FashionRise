import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import { persistMagicOperation, readMagicOperation } from '@/services/ai/magicJobStore'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'true')
vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')

const enqueueSketchPolish = vi.fn()
const settleMagicJobWithImage = vi.fn()
const captureSketchForMagic = vi.fn()

const restoredDoc: StudioDraftDocument = {
  ...createEmptyDraftDocument(),
  clientRevision: 7,
  model: 'female-straight',
  strokes: [
    {
      id: 'f1',
      tool: 'draw',
      points: [1, 2, 0.5],
      color: '#111111',
      size: 2,
      opacity: 1,
    },
  ],
  back: {
    strokes: [
      {
        id: 'b1',
        tool: 'draw',
        points: [3, 4, 0.5],
        color: '#222222',
        size: 2,
        opacity: 1,
      },
    ],
    fills: [],
  },
}

vi.mock('@/assets/rearCroquisPublished', () => ({
  REAR_CROQUIS_PUBLISHED: { 'female-straight': '/models/rear/female-straight.png' },
  isRearCroquisPublished: () => true,
}))

vi.mock('@/services/ai/magicApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/ai/magicApi')>()
  return {
    ...actual,
    enqueueSketchPolish: (...args: unknown[]) => enqueueSketchPolish(...args),
    fetchJobImageBlob: vi.fn(),
  }
})

vi.mock('@/services/ai/magicPipelineHelpers', () => ({
  settleMagicJobWithImage: (...args: unknown[]) => settleMagicJobWithImage(...args),
}))

vi.mock('@/lib/sketchCapture', () => ({
  captureSketchForMagic: (...args: unknown[]) => captureSketchForMagic(...args),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

vi.mock('@/lib/draftPersistence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/draftPersistence')>()
  return {
    ...actual,
    restoreStudioDraft: async () => ({
      designId: 'design-1',
      document: restoredDoc,
      syncedRevision: 7,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async () => ({
      ok: true as const,
      designId: 'design-1',
      document: restoredDoc,
      fingerprint: 'fp',
      syncedRevision: 7,
      localPersisted: true,
    }),
  }
})

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor retryMagicSide idempotency', () => {
  beforeEach(() => {
    sessionStorage.clear()
    enqueueSketchPolish.mockReset()
    settleMagicJobWithImage.mockReset()
    captureSketchForMagic.mockReset()
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'true')
    captureSketchForMagic.mockResolvedValue({
      blob: new Blob(['x'], { type: 'image/png' }),
      dataUrl: 'data:image/png;base64,xx',
    })
  })

  afterEach(() => {
    sessionStorage.clear()
    vi.unstubAllEnvs()
  })

  it('sends a new persisted idempotency key + operation identity on Back retry', async () => {
    const fp = draftContentFingerprint(restoredDoc)
    persistMagicOperation('u1', {
      operationId: 'op-retry',
      frontJobId: 'jf',
      backJobId: 'jb-fail',
      frontIdempotencyKey: 'op-retry:front',
      backIdempotencyKey: 'op-retry:back',
      designId: 'design-1',
      sourceRevision: 7,
      contentFingerprint: fp,
      referenceModelId: 'female-straight',
      sharedGarmentSpec: { garment_category: 'studio', main_colors: ['#111111'] },
      updatedAt: new Date().toISOString(),
    })

    enqueueSketchPolish.mockResolvedValueOnce({
      id: 'jb-retry',
      status: 'queued',
      job_type: 'sketch_polish',
      created_at: new Date().toISOString(),
      input_data: { studio_side: 'back' },
    })
    settleMagicJobWithImage.mockResolvedValueOnce({
      jobId: 'jb-retry',
      look: {
        jobId: 'jb-retry',
        status: 'completed',
        summary: 'back ok',
        bullets: [],
        hasImage: false,
      },
      lookObjectUrl: null,
    })

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => {
      result.current.retryMagicSide('back')
    })

    await waitFor(() => expect(enqueueSketchPolish).toHaveBeenCalledTimes(1))
    const arg = enqueueSketchPolish.mock.calls[0]![0] as Record<string, unknown>
    expect(arg.magic_operation_id).toBe('op-retry')
    expect(arg.studio_side).toBe('back')
    expect(String(arg.idempotency_key)).toMatch(/^op-retry:back:retry:/)
    expect(arg.source_revision).toBe(7)
    expect(arg.content_fingerprint).toBe(fp)
    expect(arg.shared_garment_spec).toEqual({
      garment_category: 'studio',
      main_colors: ['#111111'],
    })
    expect(arg.designId).toBe('design-1')
    expect(readMagicOperation('u1')?.backIdempotencyKey).toBe(arg.idempotency_key)
    expect(readMagicOperation('u1')?.backJobId).toBe('jb-retry')
  })
})
