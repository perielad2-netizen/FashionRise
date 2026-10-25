import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import { persistMagicOperation } from '@/services/ai/magicJobStore'

const resolveDualMagicJobIds = vi.fn()
const settleMagicJobWithImage = vi.fn()

vi.mock('@/services/ai/magicOperationRecovery', () => ({
  resolveDualMagicJobIds: (...args: unknown[]) => resolveDualMagicJobIds(...args),
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

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor recoverLastMagic dual lost-response', () => {
  beforeEach(() => {
    sessionStorage.clear()
    resolveDualMagicJobIds.mockReset()
    settleMagicJobWithImage.mockReset()
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  it('recovers Front/Back via operations lookup without enqueue when job ids are missing', async () => {
    persistMagicOperation('u1', {
      operationId: 'op-recover',
      frontIdempotencyKey: 'op-recover:front',
      backIdempotencyKey: 'op-recover:back',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    resolveDualMagicJobIds.mockResolvedValueOnce({
      operationId: 'op-recover',
      frontJobId: 'jf',
      backJobId: 'jb',
    })
    settleMagicJobWithImage.mockImplementation(async (jobId: string) => ({
      jobId,
      look: {
        jobId,
        status: jobId === 'jb' ? 'failed' : 'completed',
        summary: jobId === 'jb' ? 'back failed' : 'front ok',
        bullets: [],
        hasImage: jobId !== 'jb',
      },
      lookObjectUrl: jobId === 'jb' ? null : 'blob:front',
    }))

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => {
      result.current.recoverLastMagic()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('ready'))
    expect(resolveDualMagicJobIds).toHaveBeenCalledWith('u1', expect.any(AbortSignal))
    expect(settleMagicJobWithImage).toHaveBeenCalledWith('jf', expect.any(AbortSignal))
    expect(settleMagicJobWithImage).toHaveBeenCalledWith('jb', expect.any(AbortSignal))
    expect(result.current.magicDualActive).toBe(true)
    expect(result.current.magicBack.canRetry).toBe(true)
  })

  it('does not claim no previous job when only operationId is stored', async () => {
    persistMagicOperation('u1', {
      operationId: 'op-delay',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    resolveDualMagicJobIds.mockResolvedValueOnce(null)

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => {
      result.current.recoverLastMagic()
    })

    await waitFor(() => expect(result.current.magicPhase).toBe('failed'))
    expect(result.current.magicError).toMatch(/not ready yet/i)
    expect(result.current.magicError).not.toMatch(/No previous Magic job/i)
  })
})
