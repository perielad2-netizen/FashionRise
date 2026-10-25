/**
 * P1 #59 — actual useStudioEditor Magic capture lifecycle.
 * Proves reference_model_id is snapshotted before await captureSketchForMagic
 * and survives a mid-flight model switch (not just a helper-level variable copy).
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'

const magicMocks = vi.hoisted(() => {
  let releaseCapture: (() => void) | null = null
  return {
    enqueueCalls: [] as Array<{ referenceModelId: string; imageBase64: string }>,
    captureCalls: 0,
    reset() {
      this.enqueueCalls = []
      this.captureCalls = 0
      releaseCapture = null
    },
    deferCapture() {
      return new Promise<{ blob: Blob; dataUrl: string }>((resolve) => {
        releaseCapture = () =>
          resolve({
            blob: new Blob(['sketch'], { type: 'image/png' }),
            dataUrl: 'data:image/png;base64,QUJD',
          })
      })
    },
    release() {
      releaseCapture?.()
      releaseCapture = null
    },
  }
})

vi.mock('@/config/magicUi', () => ({
  isMagicUiEnabled: () => true,
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
      designId: 'draft-1',
      document: createEmptyDraftDocument(),
      syncedRevision: 1,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async (args: { designId: string | null; document: unknown }) => ({
      ok: true as const,
      designId: args.designId ?? 'draft-1',
      document: args.document,
      fingerprint: 'fp',
      syncedRevision: 1,
      localPersisted: true,
    }),
  }
})

vi.mock('@/lib/sketchCapture', () => ({
  captureSketchForMagic: async () => {
    magicMocks.captureCalls += 1
    return magicMocks.deferCapture()
  },
}))

vi.mock('@/services/ai/magicApi', () => ({
  enqueueSketchPolish: async (input: {
    referenceModelId: string
    imageBase64: string
  }) => {
    magicMocks.enqueueCalls.push({
      referenceModelId: input.referenceModelId,
      imageBase64: input.imageBase64,
    })
    return {
      id: 'job-magic-1',
      user_id: 'u1',
      design_id: null,
      job_type: 'sketch_polish',
      status: 'queued',
      input_data: {},
      result_data: null,
      error_message: null,
      created_at: '2026-10-25T00:00:00Z',
      updated_at: '2026-10-25T00:00:00Z',
    }
  },
  fetchJobImageBlob: async () => new Blob(['look'], { type: 'image/png' }),
  fetchAiJob: async () => ({
    id: 'job-magic-1',
    status: 'completed',
    result_data: { summary: 'ok', image_url: 'http://x/look.png' },
  }),
}))

vi.mock('@/services/ai/pollAiJob', () => ({
  pollAiJobUntilSettled: async () => ({
    id: 'job-magic-1',
    user_id: 'u1',
    design_id: null,
    job_type: 'sketch_polish',
    status: 'completed',
    input_data: {},
    result_data: { summary: 'ok', image_url: 'http://x/look.png' },
    error_message: null,
    created_at: '2026-10-25T00:00:00Z',
    updated_at: '2026-10-25T00:00:00Z',
  }),
}))

vi.mock('@/services/ai/magicJobStore', () => ({
  persistMagicJobId: vi.fn(),
  readMagicJobId: () => null,
  clearMagicJobId: vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor Magic capture identity snapshot', () => {
  beforeEach(() => {
    magicMocks.reset()
  })

  it('keeps the pre-capture croquis id when the model changes during async capture', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    // Start from a male library croquis (default is female-straight).
    act(() => {
      result.current.setModel('male-straight')
    })
    await waitFor(() => expect(result.current.model).toBe('male-straight'))

    act(() => {
      result.current.onMagic()
    })
    await waitFor(() => expect(magicMocks.captureCalls).toBe(1))
    expect(magicMocks.enqueueCalls).toHaveLength(0)

    // Mid-flight model switch while capture is still pending.
    act(() => {
      result.current.setModel('female-straight')
    })
    await waitFor(() => expect(result.current.model).toBe('female-straight'))

    await act(async () => {
      magicMocks.release()
    })

    await waitFor(() => expect(magicMocks.enqueueCalls).toHaveLength(1))
    expect(magicMocks.enqueueCalls[0]!.referenceModelId).toBe('male-straight')
    expect(magicMocks.enqueueCalls[0]!.imageBase64).toContain('data:image/png;base64')
    // UI model may have changed; the polish contract must keep the capture-time id.
    expect(result.current.model).toBe('female-straight')
  })
})
