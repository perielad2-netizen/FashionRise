import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { documentForCloud } from '@/services/designsApi'
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

const persistence = vi.hoisted(() => ({
  calls: [] as Array<{
    document: StudioDraftDocument
    expectedRevision: number | null
    clearBackIntent?: boolean
  }>,
  /** Gate the first N persist calls until release() is invoked. */
  gateCount: 0,
  release: null as null | (() => void),
  gatePromise: null as null | Promise<void>,
  server: null as null | StudioDraftDocument,
  designId: 'd1',
  syncedRev: 1,
  forceConflictOnce: null as null | StudioDraftDocument,
}))

vi.mock('@/lib/draftPersistence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/draftPersistence')>()
  return {
    ...actual,
    restoreStudioDraft: async () => ({
      designId: persistence.designId,
      document: persistence.server ?? createEmptyDraftDocument(),
      syncedRevision: persistence.syncedRev,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async () => ({ ok: true, wrote: true }),
    persistStudioDraft: async (args: {
      document: StudioDraftDocument
      expectedRevision: number | null
    }) => {
      persistence.calls.push({
        document: args.document,
        expectedRevision: args.expectedRevision,
        clearBackIntent: Boolean(args.document.clearBackIntent),
      })
      if (persistence.gateCount > 0 && persistence.gatePromise) {
        persistence.gateCount -= 1
        await persistence.gatePromise
      }
      if (persistence.forceConflictOnce) {
        const server = persistence.forceConflictOnce
        persistence.forceConflictOnce = null
        return {
          ok: false as const,
          conflict: {
            local: args.document,
            server,
            designId: persistence.designId,
          },
          localPersisted: true,
          error: 'Draft was updated elsewhere.',
        }
      }
      const cloud = documentForCloud(args.document)
      persistence.server = cloud
      persistence.syncedRev = cloud.clientRevision
      return {
        ok: true as const,
        designId: persistence.designId,
        document: cloud,
        fingerprint: draftContentFingerprint(cloud),
        syncedRevision: cloud.clientRevision,
        localPersisted: true,
      }
    },
  }
})

const stroke: Stroke = {
  id: 's1',
  tool: 'draw',
  points: [1, 2, 0.5, 3, 4, 0.5],
  color: '#BE185D',
  size: 2,
  opacity: 1,
}

const fillSatin: FillOp = {
  id: 'fill-satin',
  contour: [10, 10, 40, 10, 40, 40, 10, 40],
  style: { kind: 'fabric', fabricId: 'satin' },
  seedX: 20,
  seedY: 20,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('draw → undo → autosave (single session)', () => {
  beforeEach(() => {
    persistence.calls = []
    persistence.gateCount = 0
    persistence.release = null
    persistence.gatePromise = null
    persistence.server = createEmptyDraftDocument()
    persistence.syncedRev = 1
    persistence.forceConflictOnce = null
  })

  it('Back undo that empties ink stamps clearBackIntent (no false 409)', async () => {
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.changeActiveSide('back')
    })
    await waitFor(() => expect(result.current.activeSide).toBe('back'))

    // Separate acts: same-tick stroke+fill would let fill read stale empty strokes.
    act(() => {
      result.current.onStrokeComplete(stroke)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))
    act(() => {
      result.current.onFillComplete(fillSatin)
    })
    await waitFor(() => expect(result.current.fills).toHaveLength(1))

    // Flush draw/fill saves first.
    await act(async () => {
      await result.current.retrySave()
    })
    persistence.calls = []

    act(() => {
      result.current.undo() // undo fill
    })
    await waitFor(() => expect(result.current.fills).toHaveLength(0))
    act(() => {
      result.current.undo() // undo stroke → empty back
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(0))

    await act(async () => {
      await result.current.retrySave()
    })

    expect(result.current.draftConflict).toBeNull()
    const emptied = persistence.calls.find(
      (c) => c.document.back?.strokes.length === 0 && (c.document.back?.fills?.length ?? 0) === 0,
    )
    expect(emptied).toBeTruthy()
    expect(emptied?.clearBackIntent).toBe(true)
  })

  it('Front draw→undo with delayed/interleaved save does not open conflict', async () => {
    persistence.gatePromise = new Promise<void>((resolve) => {
      persistence.release = resolve
    })
    persistence.gateCount = 1

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(stroke)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))

    // Start autosave of the stroke (held by gate).
    let saveStroke: Promise<void> = Promise.resolve()
    act(() => {
      saveStroke = result.current.retrySave()
    })
    await waitFor(() => expect(persistence.calls.length).toBeGreaterThanOrEqual(1))

    // Undo while stroke save is in flight.
    act(() => {
      result.current.undo()
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(0))

    // Queue undo save behind the gated stroke save.
    let saveUndo: Promise<void> = Promise.resolve()
    act(() => {
      saveUndo = result.current.retrySave()
    })

    persistence.release?.()
    await act(async () => {
      await saveStroke
      await saveUndo
    })

    expect(result.current.draftConflict).toBeNull()
    expect(result.current.saveError).toBeNull()
    expect(result.current.strokes).toHaveLength(0)
  })

  it('stale in-flight 409 whose server already matches authoritative undo recovers without dialog', async () => {
    const empty = createEmptyDraftDocument()
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(stroke)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))

    act(() => {
      result.current.undo()
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(0))

    // Simulate stale stroke save returning 409 with server=empty (already undone on server).
    persistence.forceConflictOnce = bumpDraftDocument(empty, { model: empty.model })
    await act(async () => {
      await result.current.retrySave()
    })

    expect(result.current.draftConflict).toBeNull()
    expect(result.current.strokes).toHaveLength(0)
  })

  it('genuine multi-tab content divergence still opens conflict', async () => {
    const foreign = bumpDraftDocument(createEmptyDraftDocument(), {
      strokes: [{ ...stroke, id: 'other-tab' }],
      model: 'male-straight',
    })
    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => {
      result.current.onStrokeComplete(stroke)
    })
    await waitFor(() => expect(result.current.strokes).toHaveLength(1))

    persistence.forceConflictOnce = foreign
    await act(async () => {
      await result.current.retrySave()
    })

    expect(result.current.draftConflict).not.toBeNull()
    expect(result.current.draftConflict?.server.strokes[0]?.id).toBe('other-tab')
  })
})
