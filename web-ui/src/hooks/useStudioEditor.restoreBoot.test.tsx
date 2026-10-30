import { renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createEmptyDraftDocument,
  STUDIO_DRAFT_SCHEMA_V2,
  StudioDraftSerializeError,
} from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'

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

const v2Doc = {
  ...createEmptyDraftDocument(),
  schema: STUDIO_DRAFT_SCHEMA_V2,
  activeSide: 'front' as const,
  back: { strokes: [], fills: [] },
}

vi.mock('@/lib/draftPersistence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/draftPersistence')>()
  return {
    ...actual,
    restoreStudioDraft: async () => ({
      designId: 'design-v2',
      document: v2Doc,
      syncedRevision: 3,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async () => ({
      ok: true as const,
      designId: 'design-v2',
      document: v2Doc,
      fingerprint: 'fp',
      syncedRevision: 3,
      localPersisted: true,
    }),
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
    vi.clearAllMocks()
  })

  it('exits Restoring when V2 fingerprint serialize fails; does not stay stuck', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => {
      expect(result.current.saveStatus).not.toBe('restoring')
    })
    expect(result.current.ready).toBe(true)
    expect(result.current.saveStatus).toBe('local-only')
  })
})
