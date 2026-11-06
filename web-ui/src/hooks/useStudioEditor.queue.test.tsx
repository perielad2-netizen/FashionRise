import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument, bumpDraftDocument } from '@/lib/draftDocument'
import type { StudioDraftDocument } from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import type { Stroke } from '@/lib/strokes'

const persistence = vi.hoisted(() => ({
  designId: null as string | null,
  persistCalls: [] as Array<{ designId: string | null; strokeIds: string[] }>,
  localDocs: [] as StudioDraftDocument[],
  keepCalls: 0,
  releaseFirst: null as (() => void) | null,
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
      designId: persistence.designId,
      document: createEmptyDraftDocument(),
      syncedRevision: persistence.designId ? 1 : null,
      conflict: null,
      notice: null,
    }),
    persistLocalRecovery: async (args: { document: StudioDraftDocument }) => {
      persistence.localDocs.push(args.document)
      return { ok: true, wrote: true }
    },
    persistStudioDraft: async (args: {
      designId: string | null
      document: StudioDraftDocument
    }) => {
      persistence.persistCalls.push({
        designId: args.designId,
        strokeIds: args.document.strokes.map((stroke) => stroke.id),
      })
      if (persistence.persistCalls.length === 1) {
        await new Promise<void>((resolve) => {
          persistence.releaseFirst = resolve
        })
        const server = bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' })
        return {
          ok: false as const,
          conflict: {
            local: args.document,
            server,
            designId: args.designId ?? 'recovered-draft',
          },
          localPersisted: true,
          error: 'Draft was updated elsewhere.',
        }
      }
      return {
        ok: true as const,
        designId: args.designId ?? 'recovered-draft',
        document: args.document,
        fingerprint: 'resumed',
        syncedRevision: args.document.clientRevision,
        localPersisted: true,
      }
    },
    commitKeepDeviceChoice: async (args: {
      designId: string
      local: StudioDraftDocument
      serverRevision: number
    }) => {
      persistence.keepCalls += 1
      const rebased = actual.rebaseChosenLocalDraft(args.local, args.serverRevision)
      const { documentForCloud } = await import('@/services/designsApi')
      const { draftContentFingerprint } = await import('@/lib/draftDocument')
      return {
        ok: true as const,
        designId: args.designId,
        document: rebased,
        fingerprint: draftContentFingerprint(documentForCloud(rebased)),
        syncedRevision: rebased.clientRevision,
        localPersisted: true,
      }
    },
  }
})

const stroke: Stroke = {
  id: 'stroke-b',
  tool: 'draw',
  points: [4, 8, 1],
  color: '#112233',
  size: 4,
  opacity: 1,
}

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

async function runQueuedConflict() {
  const { result } = renderHook(() => useStudioEditor(), { wrapper })
  await waitFor(() => expect(result.current.ready).toBe(true))

  let saveA: Promise<void> = Promise.resolve()
  act(() => {
    saveA = result.current.retrySave()
  })
  await waitFor(() => expect(persistence.persistCalls).toHaveLength(1))

  act(() => {
    result.current.onStrokeComplete(stroke)
  })
  let saveB: Promise<void> = Promise.resolve()
  act(() => {
    saveB = result.current.retrySave()
  })

  persistence.releaseFirst?.()
  await act(async () => {
    await saveA
    await saveB
  })

  expect(persistence.persistCalls).toHaveLength(1)
  expect(result.current.draftConflict).not.toBeNull()
  expect(persistence.localDocs.some((doc) => doc.strokes.some((item) => item.id === 'stroke-b'))).toBe(
    true,
  )

  act(() => {
    void result.current.retrySave()
  })
  expect(persistence.persistCalls).toHaveLength(1)

  act(() => {
    result.current.resolveConflictKeepLocal()
  })
  await waitFor(() => expect(result.current.draftConflict).toBeNull())
  expect(persistence.keepCalls).toBe(1)

  await act(async () => {
    await result.current.retrySave()
  })
  expect(persistence.persistCalls).toHaveLength(2)
}

describe('queued autosave during conflict', () => {
  beforeEach(() => {
    persistence.designId = null
    persistence.persistCalls = []
    persistence.localDocs = []
    persistence.keepCalls = 0
    persistence.releaseFirst = null
  })

  it('does not let a queued save PUT an existing draft after a 409', async () => {
    persistence.designId = 'd1'
    await runQueuedConflict()
    expect(persistence.persistCalls[0]?.designId).toBe('d1')
    expect(persistence.persistCalls[1]?.designId).toBe('d1')
  })

  it('does not let a queued save reconcile a lost create after conflict', async () => {
    persistence.designId = null
    await runQueuedConflict()
    expect(persistence.persistCalls[0]?.designId).toBeNull()
    expect(persistence.persistCalls).toHaveLength(2)
  })
})
