import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'true')
vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')

const enqueueSketchPolish = vi.fn()
const enqueueDualPolish = vi.fn()
const captureSketchForMagic = vi.fn()
const settleMagicJobWithImage = vi.fn()

vi.mock('@/assets/rearCroquisPublished', () => ({
  REAR_CROQUIS_PUBLISHED: { 'female-straight': '/models/rear/female-straight.png' },
  isRearCroquisPublished: () => true,
}))

vi.mock('@/services/ai/magicApi', () => ({
  enqueueSketchPolish: (...args: unknown[]) => enqueueSketchPolish(...args),
  fetchJobImageBlob: vi.fn(),
}))

vi.mock('@/services/ai/magicDualPolish', () => ({
  DualPolishUnavailableError: class DualPolishUnavailableError extends Error {},
  enqueueDualPolish: (...args: unknown[]) => enqueueDualPolish(...args),
}))

vi.mock('@/lib/sketchCapture', () => ({
  captureSketchForMagic: (...args: unknown[]) => captureSketchForMagic(...args),
}))

vi.mock('@/services/ai/magicPipelineHelpers', () => ({
  settleMagicJobWithImage: (...args: unknown[]) => settleMagicJobWithImage(...args),
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
      designId: null,
      document: { ...createEmptyDraftDocument(), model: 'female-straight' },
      syncedRevision: null,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async () => ({
      ok: true as const,
      designId: 'd1',
      document: { ...createEmptyDraftDocument(), model: 'female-straight' },
      fingerprint: 'fp',
      syncedRevision: 1,
      localPersisted: true,
    }),
  }
})

const strokeF: Stroke = {
  id: 'f1',
  tool: 'draw',
  points: [1, 2, 0.5],
  color: '#111111',
  size: 2,
  opacity: 1,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor smart back Magic', () => {
  beforeEach(() => {
    enqueueSketchPolish.mockReset()
    enqueueDualPolish.mockReset()
    captureSketchForMagic.mockReset()
    settleMagicJobWithImage.mockReset()
    vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'true')
    vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')
    captureSketchForMagic.mockImplementation(async () => ({
      blob: new Blob(['x'], { type: 'image/png' }),
      dataUrl: 'data:image/png;base64,FRONTSEED',
    }))
    settleMagicJobWithImage.mockResolvedValue({
      jobId: 'job',
      look: {
        jobId: 'job',
        status: 'completed',
        summary: 'ok',
        bullets: [],
        hasImage: false,
      },
      lookObjectUrl: null,
    })
    enqueueDualPolish.mockResolvedValue({
      magic_operation_id: 'op1',
      front_job_id: 'front-job',
      back_job_id: 'back-job',
    })
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('enqueues Dual Magic with smart-back notes when Front has ink and Back is empty', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))
    expect(result.current.hasBackInk).toBe(false)

    await act(async () => {
      result.current.onMagic()
    })

    await waitFor(() => expect(enqueueDualPolish).toHaveBeenCalledTimes(1))
    expect(enqueueSketchPolish).not.toHaveBeenCalled()
    const payload = enqueueDualPolish.mock.calls[0]?.[0] as {
      notes: string
      back: { notes: string; image_base64: string }
      front: { notes: string }
    }
    expect(payload.notes).toMatch(/smart back completion/i)
    expect(payload.back.notes).toMatch(/Smart back completion/i)
    expect(payload.front.notes).toMatch(/Back will be inventively completed/i)
    // Seed Back from the Front capture so the model sees the garment to complete.
    expect(payload.back.image_base64).toBe('data:image/png;base64,FRONTSEED')
    expect(result.current.studioNotice).toMatch(/smart Back/i)
  })
})
