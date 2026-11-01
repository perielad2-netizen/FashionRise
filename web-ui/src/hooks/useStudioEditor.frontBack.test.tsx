import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import {
  buildDocumentFromEditor,
  sideStateFromDocument,
  switchEditorSide,
} from '@/hooks/studioEditorSides'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { FillOp } from '@/lib/fills'
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

const strokeF1: Stroke = {
  id: 'f1',
  tool: 'draw',
  points: [1, 2, 0.5],
  color: '#111111',
  size: 2,
  opacity: 1,
}

const strokeB1: Stroke = {
  id: 'b1',
  tool: 'draw',
  points: [3, 4, 0.5],
  color: '#222222',
  size: 2,
  opacity: 1,
}

const fillF: FillOp = {
  id: 'fill-f',
  contour: [10, 10, 20, 10, 20, 20, 10, 20],
  style: { kind: 'solid', color: '#ABCDEF' },
  seedX: 15,
  seedY: 15,
}

const fillB: FillOp = {
  id: 'fill-b',
  contour: [30, 30, 40, 30, 40, 40, 30, 40],
  style: { kind: 'solid', color: '#FEDCBA' },
  seedX: 35,
  seedY: 35,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('useStudioEditor front/back ownership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps front ink when switching away from back', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF1)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))
    act(() => {
      result.current.onFillComplete(fillF)
    })
    await waitFor(() => expect(result.current.fills.map((f) => f.id)).toEqual(['fill-f']))
    expect(result.current.fills.map((f) => f.id)).toEqual(['fill-f'])
    expect(result.current.fills[0]?.eraseAfterStrokeIndex).toBe(1)

    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('back'))
    act(() => {
      result.current.onStrokeComplete(strokeB1)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['b1']))
    act(() => {
      result.current.onFillComplete(fillB)
    })
    expect(result.current.strokes.map((s) => s.id)).toEqual(['b1'])
    expect(result.current.fills[0]?.eraseAfterStrokeIndex).toBe(1)

    act(() => {
      result.current.changeActiveSide('front')
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))
    expect(result.current.fills.map((f) => f.id)).toEqual(['fill-f'])
    expect(result.current.hasBackInk).toBe(true)
  })

  it('undoes independently per side', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(strokeF1)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))
    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('back'))
    act(() => {
      result.current.onStrokeComplete(strokeB1)
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['b1']))
    act(() => {
      result.current.undo()
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(0))

    act(() => {
      result.current.changeActiveSide('front')
    })
    await waitFor(() => expect(result.current.strokes.map((s) => s.id)).toEqual(['f1']))

    act(() => {
      result.current.undo()
    })
    expect(result.current.strokes).toHaveLength(0)

    act(() => {
      result.current.redo()
    })
    expect(result.current.strokes.map((s) => s.id)).toEqual(['f1'])
  })

  it('serialize round-trip preserves both sides', () => {
    const prev = createEmptyDraftDocument()
    const state = {
      activeSide: 'back' as const,
      frontStrokes: [strokeF1],
      frontFills: [fillF],
      backStrokes: [strokeB1],
      backFills: [fillB],
    }
    const doc = buildDocumentFromEditor({
      prev,
      state,
      model: 'female-straight',
      customReferenceUrl: null,
      customReferenceKey: null,
      sizeId: 'thin',
      sizePx: 2,
      opacity: 1,
      color: '#1C1C1E',
      dimmed: false,
    })
    const roundTrip = sideStateFromDocument(doc)
    expect(roundTrip.frontStrokes.map((s) => s.id)).toEqual(['f1'])
    expect(roundTrip.backStrokes.map((s) => s.id)).toEqual(['b1'])
    expect(switchEditorSide(roundTrip, 'front').frontStrokes).toHaveLength(1)
  })
})
