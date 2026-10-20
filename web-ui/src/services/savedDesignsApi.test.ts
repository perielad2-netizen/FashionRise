import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import type { DesignRead } from '@/services/designsApi'
import { buildSavedDesignPayload, snapshotFromDocument, type SavedDesignSnapshot } from '@/lib/savedDesign'
import { createEmptyDraftDocument } from '@/lib/draftDocument'

const apiRequest = vi.fn()
const listMyDesigns = vi.fn()
const getDesign = vi.fn()

vi.mock('@/services/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api/client')>()
  return { ...actual, apiRequest: (...args: unknown[]) => apiRequest(...args) }
})

vi.mock('@/services/designsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/designsApi')>()
  return {
    ...actual,
    listMyDesigns: (...args: unknown[]) => listMyDesigns(...args),
    getDesign: (...args: unknown[]) => getDesign(...args),
  }
})

const { fetchSavedDesign, saveDesignSnapshot } = await import('@/services/savedDesignsApi')

const OWNER = 'owner-1'
const snapshot: SavedDesignSnapshot = snapshotFromDocument({
  ...createEmptyDraftDocument(),
  strokes: [{ id: 's1', tool: 'draw', points: [1, 2, 0.5], color: '#1C1C1E', size: 1.75, opacity: 1 }],
})

function serverRow(id: string, saveRequestId: string, snap = snapshot, ownerId = OWNER): DesignRead {
  const payload = buildSavedDesignPayload({ title: 'Look', snapshot: snap, saveRequestId, sourceRevision: 2 })
  return {
    id,
    user_id: ownerId,
    title: payload.title,
    description: payload.description,
    garment_category: payload.garment_category,
    design_data: JSON.parse(JSON.stringify(payload.design_data)),
    metadata: payload.metadata,
    visibility: 'private',
    status: 'draft',
    created_at: '2026-10-20T10:00:00.000Z',
    updated_at: '2026-10-20T10:00:00.000Z',
  }
}

function request(overrides: Partial<Parameters<typeof saveDesignSnapshot>[0]> = {}) {
  return {
    ownerId: OWNER,
    title: 'Look',
    snapshot,
    saveRequestId: 'req-1',
    sourceRevision: 2,
    previousAttemptUncertain: false,
    ...overrides,
  }
}

beforeEach(() => {
  apiRequest.mockReset()
  listMyDesigns.mockReset()
  getDesign.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('saveDesignSnapshot idempotency', () => {
  it('creates one private envelope and reports success only on a matching acknowledgement', async () => {
    apiRequest.mockResolvedValueOnce(serverRow('d1', 'req-1'))
    const result = await saveDesignSnapshot(request())
    expect(result).toMatchObject({ ok: true, recovered: false, record: { id: 'd1' } })
    expect(apiRequest).toHaveBeenCalledTimes(1)
    const [path, options] = apiRequest.mock.calls[0]!
    expect(path).toBe('/designs')
    expect(options.method).toBe('POST')
    expect(options.body.design_data.schema).toBe('fashionrise.saved_design.v1')
    expect(options.body.metadata.draftKind).toBeUndefined()
    expect(options.body.visibility).toBe('private')
    expect(listMyDesigns).not.toHaveBeenCalled()
  })

  it('recovers a create whose response was lost without posting again', async () => {
    apiRequest.mockRejectedValueOnce(new ApiError('Unable to reach FashionRise.', 0, null))
    listMyDesigns.mockResolvedValueOnce([serverRow('d1', 'req-1')])
    const result = await saveDesignSnapshot(request())
    expect(result).toMatchObject({ ok: true, recovered: true, record: { id: 'd1' } })
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })

  it('a retry after an uncertain failure finds the earlier row instead of duplicating', async () => {
    apiRequest.mockRejectedValueOnce(new ApiError('Bad gateway', 502, null))
    listMyDesigns.mockRejectedValueOnce(new ApiError('Unable to reach FashionRise.', 0, null))
    const first = await saveDesignSnapshot(request())
    expect(first).toMatchObject({ ok: false, outcomeUncertain: true })

    listMyDesigns.mockResolvedValueOnce([serverRow('other', 'req-other'), serverRow('d1', 'req-1')])
    const retry = await saveDesignSnapshot(request({ previousAttemptUncertain: true }))
    expect(retry).toMatchObject({ ok: true, recovered: true, record: { id: 'd1' } })
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })

  it('a retry posts once when the earlier attempt provably did not land', async () => {
    listMyDesigns.mockResolvedValueOnce([serverRow('other', 'req-other')])
    apiRequest.mockResolvedValueOnce(serverRow('d2', 'req-1'))
    const retry = await saveDesignSnapshot(request({ previousAttemptUncertain: true }))
    expect(retry).toMatchObject({ ok: true, recovered: false, record: { id: 'd2' } })
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })

  it('never posts blindly when the earlier outcome cannot be checked', async () => {
    listMyDesigns.mockRejectedValueOnce(new ApiError('Unable to reach FashionRise.', 0, null))
    const retry = await saveDesignSnapshot(request({ previousAttemptUncertain: true }))
    expect(retry).toMatchObject({ ok: false, outcomeUncertain: true })
    expect(apiRequest).not.toHaveBeenCalled()
  })

  it('a validation rejection is final and not treated as uncertain', async () => {
    apiRequest.mockRejectedValueOnce(new ApiError('Title too long', 422, null))
    const result = await saveDesignSnapshot(request())
    expect(result).toMatchObject({ ok: false, outcomeUncertain: false, error: 'Title too long' })
    expect(listMyDesigns).not.toHaveBeenCalled()
  })

  it('offline: no request and no false success', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    const result = await saveDesignSnapshot(request())
    expect(result.ok).toBe(false)
    expect(apiRequest).not.toHaveBeenCalled()
    expect(listMyDesigns).not.toHaveBeenCalled()
  })

  it('does not report success when the acknowledged snapshot differs', async () => {
    const other = { ...snapshot, model: 'blank' as const }
    apiRequest.mockResolvedValueOnce(serverRow('d1', 'req-1', other))
    const result = await saveDesignSnapshot(request())
    expect(result).toMatchObject({ ok: false, outcomeUncertain: true })
  })

  it('ignores a matching request id that belongs to another account', async () => {
    listMyDesigns.mockResolvedValueOnce([serverRow('foreign', 'req-1', snapshot, 'intruder')])
    apiRequest.mockResolvedValueOnce(serverRow('d3', 'req-1'))
    const retry = await saveDesignSnapshot(request({ previousAttemptUncertain: true }))
    expect(retry).toMatchObject({ ok: true, record: { id: 'd3' } })
  })
})

describe('fetchSavedDesign', () => {
  it('returns an owner-private saved design', async () => {
    getDesign.mockResolvedValueOnce(serverRow('d1', 'req-1'))
    await expect(fetchSavedDesign(OWNER, 'd1')).resolves.toMatchObject({ ok: true, record: { id: 'd1' } })
  })

  it('refuses another account, a working draft or a malformed envelope', async () => {
    getDesign.mockResolvedValueOnce(serverRow('d1', 'req-1', snapshot, 'someone-else'))
    await expect(fetchSavedDesign(OWNER, 'd1')).resolves.toMatchObject({ ok: false, reason: 'invalid' })

    getDesign.mockResolvedValueOnce({
      ...serverRow('d2', 'req-2'),
      design_data: { ...createEmptyDraftDocument() },
      metadata: { draftKind: 'studio_working_draft' },
    })
    await expect(fetchSavedDesign(OWNER, 'd2')).resolves.toMatchObject({ ok: false, reason: 'invalid' })

    const broken = serverRow('d3', 'req-3')
    broken.design_data = { ...broken.design_data, snapshot: { strokes: [{ tool: 'draw' }] } }
    getDesign.mockResolvedValueOnce(broken)
    await expect(fetchSavedDesign(OWNER, 'd3')).resolves.toMatchObject({ ok: false, reason: 'invalid' })
  })

  it('maps 404 and network failures', async () => {
    getDesign.mockRejectedValueOnce(new ApiError('Design not found', 404, null))
    await expect(fetchSavedDesign(OWNER, 'x')).resolves.toMatchObject({ ok: false, reason: 'not-found' })
    getDesign.mockRejectedValueOnce(new ApiError('Unable to reach FashionRise.', 0, null))
    await expect(fetchSavedDesign(OWNER, 'x')).resolves.toMatchObject({ ok: false, reason: 'network' })
  })
})
