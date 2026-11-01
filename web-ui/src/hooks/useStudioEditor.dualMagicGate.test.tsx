import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'false')
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
      document: createEmptyDraftDocument(),
      syncedRevision: null,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async () => ({
      ok: true as const,
      designId: 'd1',
      document: createEmptyDraftDocument(),
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

const strokeB: Stroke = {
  id: 'b1',
  tool: 'draw',
  points: [3, 4, 0.5],
  color: '#222222',
  size: 2,
  opacity: 1,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor Dual Magic gate (default off)', () => {
  beforeEach(() => {
    enqueueSketchPolish.mockReset()
    enqueueDualPolish.mockReset()
    captureSketchForMagic.mockReset()
    settleMagicJobWithImage.mockReset()
    vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'false')
    vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('shows Front/Back Magic coming soon when Back ink is present and does not enqueue', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))

    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('back'))

    act(() => {
      result.current.onStrokeComplete(strokeB)
    })
    await waitFor(() => expect(result.current.hasBackInk).toBe(true))

    act(() => {
      result.current.onMagic()
    })

    expect(result.current.comingSoon).toBe('Front/Back Magic coming soon')
    expect(enqueueDualPolish).not.toHaveBeenCalled()
    expect(enqueueSketchPolish).not.toHaveBeenCalled()
    expect(captureSketchForMagic).not.toHaveBeenCalled()
    expect(result.current.magicOpen).toBe(false)
  })

  it('still enqueues ordinary Front-only Magic when Dual Magic is off', async () => {
    enqueueSketchPolish.mockResolvedValueOnce({ id: 'job-front' })
    captureSketchForMagic.mockResolvedValueOnce({
      blob: new Blob(['x'], { type: 'image/png' }),
      dataUrl: 'data:image/png;base64,xx',
    })
    settleMagicJobWithImage.mockResolvedValueOnce({
      jobId: 'job-front',
      look: {
        jobId: 'job-front',
        status: 'completed',
        summary: 'ok',
        bullets: [],
        hasImage: false,
      },
      lookObjectUrl: null,
    })

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

    await waitFor(() => expect(enqueueSketchPolish).toHaveBeenCalledTimes(1))
    expect(enqueueDualPolish).not.toHaveBeenCalled()
    expect(result.current.comingSoon).toBeNull()
  })
})
