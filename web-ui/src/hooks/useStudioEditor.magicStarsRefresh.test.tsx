import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useSyncExternalStore, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'
import { persistMagicJobId } from '@/services/ai/magicJobStore'
import { useAuth } from '@/services/auth/AuthProvider'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'false')
vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')

const enqueueSketchPolish = vi.fn()
const captureSketchForMagic = vi.fn()
const settleMagicJobWithImage = vi.fn()
const recoverMagicJob = vi.fn()
const fetchJobImageBlob = vi.fn()

const authStore = vi.hoisted(() => {
  type User = {
    id: string
    username: string
    ai_stars: number
    ai_stars_unlimited?: boolean
  }
  let user: User = { id: 'u1', username: 'demo', ai_stars: 1_000_089 }
  const listeners = new Set<() => void>()
  const refreshUser = vi.fn(async () => {
    // Server-authoritative post-debit balance — never invent a local −10.
    user = { ...user, ai_stars: 1_000_079 }
    listeners.forEach((l) => l())
  })
  return {
    getSnapshot: () => user,
    subscribe: (listener: () => void) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    setUser: (next: User) => {
      user = next
      listeners.forEach((l) => l())
    },
    reset: () => {
      user = { id: 'u1', username: 'demo', ai_stars: 1_000_089 }
      refreshUser.mockReset()
      refreshUser.mockImplementation(async () => {
        user = { ...user, ai_stars: 1_000_079 }
        listeners.forEach((l) => l())
      })
      listeners.forEach((l) => l())
    },
    refreshUser,
  }
})

vi.mock('@/assets/rearCroquisPublished', () => ({
  REAR_CROQUIS_PUBLISHED: { 'female-straight': '/models/rear/female-straight.png' },
  isRearCroquisPublished: () => true,
}))

vi.mock('@/services/ai/magicApi', () => ({
  enqueueSketchPolish: (...args: unknown[]) => enqueueSketchPolish(...args),
  fetchJobImageBlob: (...args: unknown[]) => fetchJobImageBlob(...args),
}))

vi.mock('@/services/ai/pollAiJob', () => ({
  recoverMagicJob: (...args: unknown[]) => recoverMagicJob(...args),
}))

vi.mock('@/services/ai/magicPipelineHelpers', () => ({
  settleMagicJobWithImage: (...args: unknown[]) => settleMagicJobWithImage(...args),
}))

vi.mock('@/lib/sketchCapture', () => ({
  captureSketchForMagic: (...args: unknown[]) => captureSketchForMagic(...args),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => {
    const user = useSyncExternalStore(authStore.subscribe, authStore.getSnapshot)
    return {
      user,
      logout: vi.fn(),
      refreshUser: authStore.refreshUser,
      isAuthenticated: Boolean(user),
      bootstrapping: false,
    }
  },
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

function StarsProbe() {
  const { user } = useAuth()
  return <div data-testid="stars-balance">{user?.ai_stars ?? 'none'}</div>
}

describe('useStudioEditor Magic Stars balance refresh', () => {
  beforeEach(() => {
    sessionStorage.clear()
    authStore.reset()
    enqueueSketchPolish.mockReset()
    captureSketchForMagic.mockReset()
    settleMagicJobWithImage.mockReset()
    recoverMagicJob.mockReset()
    fetchJobImageBlob.mockReset()
    vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', 'false')
    vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'true')
    captureSketchForMagic.mockResolvedValue({
      blob: new Blob(['x'], { type: 'image/png' }),
      dataUrl: 'data:image/png;base64,SKETCH',
    })
    enqueueSketchPolish.mockResolvedValue({ id: 'job-magic-1' })
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    sessionStorage.clear()
  })

  it('updates visible Stars from 1000089 → 1000079 after Magic completes without navigation', async () => {
    settleMagicJobWithImage.mockImplementation(async () => {
      // Debit is committed on the server only when the job settles successfully.
      expect(authStore.refreshUser).not.toHaveBeenCalled()
      return {
        jobId: 'job-magic-1',
        look: {
          jobId: 'job-magic-1',
          status: 'completed',
          summary: 'ok',
          bullets: [],
          hasImage: false,
        },
        lookObjectUrl: null,
      }
    })

    render(<StarsProbe />, { wrapper })
    expect(screen.getByTestId('stars-balance')).toHaveTextContent('1000089')

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))

    await act(async () => {
      result.current.onMagic()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('ready'))
    expect(enqueueSketchPolish).toHaveBeenCalledTimes(1)
    expect(settleMagicJobWithImage).toHaveBeenCalledTimes(1)
    expect(authStore.refreshUser).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByTestId('stars-balance')).toHaveTextContent('1000079'))
  })

  it('does not fabricate a Stars debit when Magic fails', async () => {
    settleMagicJobWithImage.mockResolvedValue({
      jobId: 'job-fail',
      look: {
        jobId: 'job-fail',
        status: 'failed',
        summary: 'provider error',
        bullets: [],
        hasImage: false,
      },
      lookObjectUrl: null,
    })

    render(<StarsProbe />, { wrapper })
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))

    await act(async () => {
      result.current.onMagic()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('failed'))
    expect(authStore.refreshUser).not.toHaveBeenCalled()
    expect(screen.getByTestId('stars-balance')).toHaveTextContent('1000089')
  })

  it('does not refresh Stars when Magic wait is cancelled', async () => {
    settleMagicJobWithImage.mockImplementation(async (_id: string, signal?: AbortSignal) => {
      return await new Promise((_resolve, reject) => {
        const onAbort = () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
        if (signal?.aborted) {
          onAbort()
          return
        }
        signal?.addEventListener('abort', onAbort, { once: true })
      })
    })

    render(<StarsProbe />, { wrapper })
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))

    await act(async () => {
      result.current.onMagic()
    })
    await waitFor(() => expect(result.current.magicPhase).toBe('polling'))

    await act(async () => {
      result.current.cancelMagicWait()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('failed'))
    expect(authStore.refreshUser).not.toHaveBeenCalled()
    expect(screen.getByTestId('stars-balance')).toHaveTextContent('1000089')
  })

  it('refreshes Stars after recovering a successful completed Magic job', async () => {
    persistMagicJobId('u1', 'job-recovered')
    recoverMagicJob.mockResolvedValue({
      id: 'job-recovered',
      user_id: 'u1',
      design_id: null,
      job_type: 'sketch_polish',
      status: 'completed',
      input_data: {},
      result_data: { summary: 'ok', bullets: [] },
      error_message: null,
      created_at: '2026-11-11T00:00:00Z',
      updated_at: '2026-11-11T00:00:00Z',
    })

    render(<StarsProbe />, { wrapper })
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => {
      result.current.recoverLastMagic()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('ready'))
    expect(recoverMagicJob).toHaveBeenCalled()
    expect(authStore.refreshUser).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByTestId('stars-balance')).toHaveTextContent('1000079'))
  })
})
