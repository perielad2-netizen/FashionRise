/**
 * V2-0030 — rectangular eraser commits on the active paper side only and undoes cleanly.
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')

vi.mock('@/assets/rearCroquisPublished', () => ({
  REAR_CROQUIS_PUBLISHED: {},
  isRearCroquisPublished: () => true,
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    refreshUser: vi.fn(async () => undefined),
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

const strokeFront: Stroke = {
  id: 'front-in',
  tool: 'draw',
  points: [10, 10, 1, 20, 20, 1],
  color: '#111111',
  size: 3,
  opacity: 1,
}

const strokeFrontOut: Stroke = {
  id: 'front-out',
  tool: 'draw',
  points: [200, 200, 1, 220, 220, 1],
  color: '#111111',
  size: 3,
  opacity: 1,
}

const strokeBack: Stroke = {
  id: 'back-in',
  tool: 'draw',
  points: [12, 12, 1, 18, 18, 1],
  color: '#222222',
  size: 3,
  opacity: 1,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor rectangular eraser (V2-0030)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('erases Front selection only; Back ink stays; Undo restores Front', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeFront)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['front-in']))
    act(() => {
      result.current.onStrokeComplete(strokeFrontOut)
    })
    await waitFor(() =>
      expect(result.current.strokes.map((s) => s.id)).toEqual(['front-in', 'front-out']),
    )

    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('back'))

    act(() => {
      result.current.onStrokeComplete(strokeBack)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['back-in']))

    act(() => {
      result.current.changeActiveSide('front')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('front'))

    act(() => {
      result.current.onRectEraseComplete({ x: 5, y: 5, width: 40, height: 40 })
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['front-out']))

    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['back-in']))

    act(() => {
      result.current.changeActiveSide('front')
    })
    act(() => {
      result.current.undo()
    })
    await waitFor(() =>
      expect(result.current.strokes.map((s) => s.id)).toEqual(['front-in', 'front-out']),
    )
  })

  it('keeps Clear canvas available as a separate path', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => {
      result.current.onStrokeComplete(strokeFront)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))
    act(() => {
      result.current.clear()
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(0))
  })
})
