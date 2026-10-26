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
  createTechpackDraft,
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
})
