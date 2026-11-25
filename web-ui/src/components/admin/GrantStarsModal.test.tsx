import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GrantStarsModal } from './GrantStarsModal'

const postAdminStarsGrant = vi.fn()
const fetchAdminStarsGrantLimits = vi.fn()
const readPendingStarsGrant = vi.fn()
const writePendingStarsGrant = vi.fn()
const clearPendingStarsGrant = vi.fn()
const pendingMatchesPayload = vi.fn()
const buildPendingStarsGrant = vi.fn()

vi.mock('@/services/adminApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/adminApi')>(
    '@/services/adminApi',
  )
  return {
    ...actual,
    postAdminStarsGrant: (...args: unknown[]) => postAdminStarsGrant(...args),
    fetchAdminStarsGrantLimits: (...args: unknown[]) => fetchAdminStarsGrantLimits(...args),
    readPendingStarsGrant: (...args: unknown[]) => readPendingStarsGrant(...args),
    writePendingStarsGrant: (...args: unknown[]) => writePendingStarsGrant(...args),
    clearPendingStarsGrant: (...args: unknown[]) => clearPendingStarsGrant(...args),
    pendingMatchesPayload: (...args: unknown[]) => pendingMatchesPayload(...args),
    buildPendingStarsGrant: (...args: unknown[]) => buildPendingStarsGrant(...args),
  }
})

const customer = {
  id: 'user-1',
  username: 'shopper',
  email: 'shopper@example.com',
  classification: 'CUSTOMER' as const,
  wallet: {
    ai_stars: 10,
    ai_stars_unlimited: false,
    ai_stars_iap_debt: 0,
  },
}

describe('GrantStarsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchAdminStarsGrantLimits.mockResolvedValue({
      max_per_transaction: 10_000,
      absolute_ceiling: 50_000,
      large_confirm_threshold: 500,
      reasons: ['CUSTOMER_APPRECIATION'],
    })
    readPendingStarsGrant.mockReturnValue(null)
    pendingMatchesPayload.mockReturnValue(true)
    buildPendingStarsGrant.mockImplementation((input: Record<string, unknown>) => ({
      ...input,
      noteFingerprint: '0:0',
      createdAt: new Date().toISOString(),
    }))
  })

  it('requires review confirmation before granting', async () => {
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '+50' }))
    fireEvent.click(screen.getByRole('button', { name: /Review grant/i }))
    expect(screen.getByText(/You are about to grant/i)).toBeTruthy()
    expect(postAdminStarsGrant).not.toHaveBeenCalled()
  })

  it('ignores rapid double confirm clicks (sync lock)', async () => {
    let resolveGrant: (v: unknown) => void = () => undefined
    postAdminStarsGrant.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGrant = resolve
        }),
    )
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '+50' }))
    fireEvent.click(screen.getByRole('button', { name: /Review grant/i }))
    const confirm = await screen.findByRole('button', { name: /Confirm & Grant 50 Stars/i })
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalledTimes(1))
    resolveGrant({
      grant_id: 'g1',
      recipient_id: 'user-1',
      actor_id: 'admin-1',
      amount: 50,
      balance_before: 10,
      balance_after: 60,
      reason: 'CUSTOMER_APPRECIATION',
      note: null,
      source: 'ADMIN_GRANT',
      status: 'completed',
      idempotency_key: 'k',
      created_at: null,
    })
    await screen.findByText(/Stars granted successfully/i)
  })

  it('reuses pending idempotency key after uncertain network outcome', async () => {
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-pending-key-01',
      createdAt: new Date().toISOString(),
    })
    postAdminStarsGrant.mockRejectedValueOnce(new Error('network dropped'))
    postAdminStarsGrant.mockResolvedValueOnce({
      grant_id: 'g2',
      recipient_id: 'user-1',
      actor_id: 'admin-1',
      amount: 50,
      balance_before: 10,
      balance_after: 60,
      reason: 'CUSTOMER_APPRECIATION',
      note: null,
      source: 'ADMIN_GRANT',
      status: 'completed',
      idempotency_key: 'grant-pending-key-01',
      created_at: null,
      idempotent_replay: true,
    })
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    // Pending recovery jumps to confirm.
    await screen.findByText(/Pending grant recovery active/i)
    const confirm = await screen.findByRole('button', { name: /Confirm & Grant 50 Stars/i })
    fireEvent.click(confirm)
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalled())
    expect(postAdminStarsGrant.mock.calls[0][1].idempotency_key).toBe('grant-pending-key-01')
    // Retry after uncertain outcome still uses same key.
    fireEvent.click(await screen.findByRole('button', { name: /Confirm & Grant 50 Stars/i }))
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalledTimes(2))
    expect(postAdminStarsGrant.mock.calls[1][1].idempotency_key).toBe('grant-pending-key-01')
  })

  it('blocks close while request is in flight', async () => {
    postAdminStarsGrant.mockImplementation(() => new Promise(() => undefined))
    const onClose = vi.fn()
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={onClose}
        onGranted={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '+25' }))
    fireEvent.click(screen.getByRole('button', { name: /Review grant/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Confirm & Grant 25 Stars/i }))
    const closeBtn = screen.getByRole('button', { name: /^Close$/i })
    expect(closeBtn).toHaveProperty('disabled', true)
    fireEvent.click(closeBtn)
    expect(onClose).not.toHaveBeenCalled()
  })
})
