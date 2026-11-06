import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createEmptyDraftDocument,
  STUDIO_DRAFT_SCHEMA_V2,
  StudioDraftSerializeError,
} from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'false')
vi.stubEnv('VITE_MAGIC_UI_ENABLED', 'false')

vi.mock('@/assets/rearCroquisPublished', () => ({
  REAR_CROQUIS_PUBLISHED: {},
  isRearCroquisPublished: () => false,
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

const backInk: Stroke = {
  id: 'back-ink-1',
  tool: 'draw',
  points: [10, 20, 0.5, 30, 40, 0.5],
  color: '#112233',
  size: 2,
  opacity: 1,
}

const v2Doc = {
  ...createEmptyDraftDocument(),
  schema: STUDIO_DRAFT_SCHEMA_V2,
  activeSide: 'front' as const,
  back: { strokes: [backInk], fills: [] },
}

const persistStudioDraft = vi.fn(async () => ({
  ok: true as const,
  designId: 'design-v2',
  document: v2Doc,
  fingerprint: 'fp',
  syncedRevision: 3,
  localPersisted: true,
}))

const restoreStudioDraft = vi.fn(async () => ({
  designId: 'design-v2',
  document: v2Doc,
  syncedRevision: 3,
  conflict: null,
  notice: null,
}))

vi.mock('@/lib/draftPersistence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/draftPersistence')>()
  return {
    ...actual,
    restoreStudioDraft: (...args: unknown[]) => restoreStudioDraft(...args),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: (...args: unknown[]) => persistStudioDraft(...args),
  }
})

vi.mock('@/services/designsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/designsApi')>()
  return {
    ...actual,
    documentForCloud: () => {
      throw new StudioDraftSerializeError(
        'Front/Back is disabled; refusing to downgrade or strip a v2 studio draft.',
      )
    },
  }
})

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor restore boot (#136)', () => {
  beforeEach(() => {
    persistStudioDraft.mockClear()
    restoreStudioDraft.mockClear()
    restoreStudioDraft.mockImplementation(async () => ({
      designId: 'design-v2',
      document: v2Doc,
      syncedRevision: 3,
      conflict: null,
      notice: null,
    }))
  })

  it('keeps V2 back ink, exits Restoring, and never cloud-writes after serialize block', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => {
      expect(result.current.saveStatus).not.toBe('restoring')
    })
    expect(result.current.ready).toBe(true)
    expect(result.current.saveStatus).toBe('local-only')
    expect(result.current.hasBackInk).toBe(true)
    expect(result.current.studioNotice ?? '').toMatch(/Front\/Back/i)
    expect(result.current.studioNotice ?? '').toMatch(/not overwritten/i)
    expect(persistStudioDraft).not.toHaveBeenCalled()

    // Ordinary UI action must still refuse automatic cloud overwrite.
    await act(async () => {
      result.current.retrySave()
    })
    await waitFor(() => {
      expect(persistStudioDraft).not.toHaveBeenCalled()
    })
  })

  it('exits Restoring with actionable error on generic restore rejection; no cloud write', async () => {
    restoreStudioDraft.mockImplementationOnce(async () => {
      throw new Error('indexeddb unavailable')
    })
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => {
      expect(result.current.saveStatus).not.toBe('restoring')
    })
    expect(result.current.ready).toBe(true)
    expect(result.current.saveStatus).toBe('error')
    expect(result.current.saveStatusLabel).toMatch(/Save failed/i)
    expect(result.current.studioNotice ?? '').toMatch(/not overwritten/i)
    expect(persistStudioDraft).not.toHaveBeenCalled()
  })
})
