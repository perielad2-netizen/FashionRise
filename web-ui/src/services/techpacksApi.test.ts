import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()
const getApiBaseUrl = vi.fn(() => 'https://api.test/api/v1')
const tokenStoreGet = vi.fn(() => ({ accessToken: 'tok' }))

vi.mock('@/services/api/client', () => ({
  ApiError: class ApiError extends Error {
    status: number
    body: unknown
    constructor(message: string, status: number, body: unknown) {
      super(message)
      this.status = status
      this.body = body
    }
  },
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  getApiBaseUrl: () => getApiBaseUrl(),
}))

vi.mock('@/services/auth/tokenStore', () => ({
  tokenStore: { get: () => tokenStoreGet() },
}))

import {
  confirmTechpackAi,
  createTechpackDraft,
  generateTechpackAi,
  getTechpackAiRun,
  getTechpackAiStatus,
  listTechpackDrafts,
  openOrCreateTechpackForLook,
  updateTechpackDraft,
} from '@/services/techpacksApi'

describe('techpacksApi', () => {
  beforeEach(() => {
    apiRequest.mockReset()
  })

  it('creates a draft for a look', async () => {
    apiRequest.mockResolvedValueOnce({ id: 'd1', look_id: 'look-1' })
    await createTechpackDraft('look-1', 'Title')
    expect(apiRequest).toHaveBeenCalledWith('/techpacks', {
      method: 'POST',
      body: { look_id: 'look-1', title: 'Title' },
    })
  })

  it('reopens an existing draft instead of creating', async () => {
    apiRequest
      .mockResolvedValueOnce({ items: [{ id: 'existing' }], total: 1, limit: 1, offset: 0 })
    const draft = await openOrCreateTechpackForLook('look-1')
    expect(draft.id).toBe('existing')
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })

  it('creates when none exist for the look', async () => {
    apiRequest
      .mockResolvedValueOnce({ items: [], total: 0, limit: 1, offset: 0 })
      .mockResolvedValueOnce({ id: 'new-draft' })
    const draft = await openOrCreateTechpackForLook('look-2', 'Look two')
    expect(draft.id).toBe('new-draft')
    expect(apiRequest).toHaveBeenCalledTimes(2)
  })

  it('lists and patches drafts', async () => {
    apiRequest.mockResolvedValueOnce({ items: [], total: 0, limit: 24, offset: 0 })
    await listTechpackDrafts({ lookId: 'look-9' })
    expect(apiRequest.mock.calls[0][0]).toContain('look_id=look-9')

    apiRequest.mockResolvedValueOnce({ id: 'd1' })
    await updateTechpackDraft('d1', { title: 'Renamed', bump_revision: true })
    expect(apiRequest).toHaveBeenLastCalledWith('/techpacks/d1', {
      method: 'PATCH',
      body: { title: 'Renamed', bump_revision: true },
    })
  })

  it('fetches AI status', async () => {
    apiRequest.mockResolvedValueOnce({ enabled: false, note: 'heuristic only' })
    const status = await getTechpackAiStatus()
    expect(status.enabled).toBe(false)
    expect(apiRequest).toHaveBeenCalledWith('/techpacks/ai/status', {
      method: 'GET',
      signal: undefined,
    })
  })

  it('confirms and generates AI runs', async () => {
    apiRequest.mockResolvedValueOnce({
      draft_id: 'd1',
      stage: 'generate',
      confirm_token: 'tok-12345678',
      estimated_cost_usd_cents: 0,
      ai_enabled: false,
      message: 'Heuristic available',
    })
    const confirm = await confirmTechpackAi('d1', 'generate')
    expect(confirm.confirm_token).toBe('tok-12345678')
    expect(apiRequest).toHaveBeenLastCalledWith('/techpacks/d1/ai/confirm', {
      method: 'POST',
      body: { stage: 'generate' },
    })

    apiRequest.mockResolvedValueOnce({
      run_id: 'run-1',
      status: 'completed',
      cost_usd_cents: 0,
      mode: 'heuristic',
    })
    await generateTechpackAi('d1', {
      confirm_token: 'tok-12345678',
      idempotency_key: 'idem-abcdef',
      mode: 'heuristic',
    })
    expect(apiRequest).toHaveBeenLastCalledWith('/techpacks/d1/ai/generate', {
      method: 'POST',
      body: {
        confirm_token: 'tok-12345678',
        idempotency_key: 'idem-abcdef',
        mode: 'heuristic',
      },
    })

    apiRequest.mockResolvedValueOnce({ id: 'run-1', status: 'completed', cost_usd_cents: 0 })
    await getTechpackAiRun('run-1')
    expect(apiRequest).toHaveBeenLastCalledWith('/techpacks/ai/runs/run-1', {
      method: 'GET',
      signal: undefined,
    })
  })
})
