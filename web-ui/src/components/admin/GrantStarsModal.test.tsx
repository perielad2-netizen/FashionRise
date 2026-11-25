import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import { GrantStarsModal } from './GrantStarsModal'

const postAdminStarsGrant = vi.fn()
const fetchAdminStarsGrantLimits = vi.fn()
const fetchAdminStarsGrantByIdempotency = vi.fn()
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
    fetchAdminStarsGrantByIdempotency: (...args: unknown[]) =>
      fetchAdminStarsGrantByIdempotency(...args),
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

const customerB = {
  ...customer,
  id: 'user-2',
  username: 'other',
  email: 'other@example.com',
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
    writePendingStarsGrant.mockReturnValue({ ok: true })
    buildPendingStarsGrant.mockImplementation((input: Record<string, unknown>) => ({
      ...input,
      noteFingerprint: '0:0',
      createdAt: new Date().toISOString(),
    }))
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'not_found',
      message: 'No completed grant',
      grant: null,
      wallet: null,
      wallet_mutations: 0,
    })
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

  it('blocks customer B when customer A pending is unresolved', async () => {
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'customer-a',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-customer-a-key',
      createdAt: new Date().toISOString(),
    })
    render(
      <GrantStarsModal
        customer={customerB}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    await screen.findByText(/unresolved Stars grant for another customer/i)
    expect(postAdminStarsGrant).not.toHaveBeenCalled()
    expect(fetchAdminStarsGrantByIdempotency).not.toHaveBeenCalled()
  })

  it('reconciles recorded grant after refresh without posting again', async () => {
    const onGranted = vi.fn()
    const onWalletRefresh = vi.fn()
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-pending-key-01',
      createdAt: new Date().toISOString(),
    })
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'recorded',
      message: 'Completed grant recorded',
      grant: {
        grant_id: 'g-recorded',
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
      },
      wallet: {
        recipient_id: 'user-1',
        ai_stars: 60,
        ai_stars_unlimited: false,
        ai_stars_iap_debt: 0,
      },
      wallet_mutations: 0,
    })
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={onGranted}
        onWalletRefresh={onWalletRefresh}
      />,
    )
    await screen.findByText(/Stars granted successfully/i)
    expect(postAdminStarsGrant).not.toHaveBeenCalled()
    expect(clearPendingStarsGrant).toHaveBeenCalledWith('grant-pending-key-01')
    expect(onGranted).toHaveBeenCalled()
    expect(onWalletRefresh).toHaveBeenCalledWith(
      expect.objectContaining({ ai_stars: 60 }),
    )
  })

  it('requires note re-entry after refresh when original grant had a note', async () => {
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'OTHER',
      noteFingerprint: '12:12345',
      idempotencyKey: 'grant-note-key',
      createdAt: new Date().toISOString(),
    })
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'not_found',
      message: 'No completed grant recorded',
      grant: null,
      wallet: null,
      wallet_mutations: 0,
    })
    pendingMatchesPayload.mockReturnValue(false)
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    await screen.findByText(/Re-enter the exact original note/i)
    const confirm = await screen.findByRole('button', {
      name: /Reconcile \/ Confirm 50 Stars/i,
    })
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(
        screen.getByText(/explanatory note is required|original internal note|exact original note/i),
      ).toBeTruthy(),
    )
    expect(postAdminStarsGrant).not.toHaveBeenCalled()
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
    fetchAdminStarsGrantByIdempotency
      .mockResolvedValueOnce({
        outcome: 'not_found',
        message: 'No completed grant',
        grant: null,
        wallet: null,
        wallet_mutations: 0,
      })
      .mockResolvedValueOnce({
        outcome: 'not_found',
        message: 'No completed grant',
        grant: null,
        wallet: null,
        wallet_mutations: 0,
      })
      .mockResolvedValueOnce({
        outcome: 'not_found',
        message: 'No completed grant',
        grant: null,
        wallet: null,
        wallet_mutations: 0,
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
    await screen.findByText(/Pending grant recovery active/i)
    const confirm = await screen.findByRole('button', {
      name: /Reconcile \/ Confirm 50 Stars/i,
    })
    fireEvent.click(confirm)
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalled())
    expect(postAdminStarsGrant.mock.calls[0][1].idempotency_key).toBe('grant-pending-key-01')
    fireEvent.click(
      await screen.findByRole('button', { name: /Reconcile \/ Confirm 50 Stars/i }),
    )
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalledTimes(2))
    expect(postAdminStarsGrant.mock.calls[1][1].idempotency_key).toBe('grant-pending-key-01')
  })

  it('clears pending on definitive first-attempt rejection', async () => {
    postAdminStarsGrant.mockRejectedValueOnce(
      new ApiError('amount must be a strictly positive integer', 422, null),
    )
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '+25' }))
    fireEvent.click(screen.getByRole('button', { name: /Review grant/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Confirm & Grant 25 Stars/i }))
    await waitFor(() => expect(clearPendingStarsGrant).toHaveBeenCalled())
    await screen.findByText(/rejection is definitive/i)
  })

  it('keeps original pending key when uncertain recovery retry returns 4xx', async () => {
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-uncertain-key',
      createdAt: new Date().toISOString(),
    })
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'not_found',
      message: 'No completed grant',
      grant: null,
      wallet: null,
      wallet_mutations: 0,
    })
    postAdminStarsGrant.mockRejectedValueOnce(
      new ApiError('Cannot grant while outstanding IAP Stars debt exists', 403, null),
    )
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    await screen.findByText(/Pending grant recovery active/i)
    fireEvent.click(
      await screen.findByRole('button', { name: /Reconcile \/ Confirm 50 Stars/i }),
    )
    await waitFor(() => expect(postAdminStarsGrant).toHaveBeenCalled())
    expect(postAdminStarsGrant.mock.calls[0][1].idempotency_key).toBe('grant-uncertain-key')
    expect(clearPendingStarsGrant).not.toHaveBeenCalled()
    await screen.findByText(/pending recovery was preserved/i)
    expect(postAdminStarsGrant.mock.calls[0][1].idempotency_key).toBe('grant-uncertain-key')
  })

  it('passes authoritative current wallet to onGranted on reconcile', async () => {
    const onGranted = vi.fn()
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-wallet-auth',
      createdAt: new Date().toISOString(),
    })
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'recorded',
      message: 'Completed',
      grant: {
        grant_id: 'g-auth',
        recipient_id: 'user-1',
        actor_id: 'admin-1',
        amount: 50,
        balance_before: 10,
        balance_after: 60,
        reason: 'CUSTOMER_APPRECIATION',
        note: null,
        source: 'ADMIN_GRANT',
        status: 'completed',
        idempotency_key: 'grant-wallet-auth',
        created_at: null,
        idempotent_replay: true,
      },
      wallet: {
        recipient_id: 'user-1',
        ai_stars: 42,
        ai_stars_unlimited: false,
        ai_stars_iap_debt: 0,
      },
      wallet_mutations: 0,
    })
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={onGranted}
      />,
    )
    await screen.findByText(/Stars granted successfully/i)
    expect(onGranted).toHaveBeenCalledWith(
      expect.objectContaining({ grant_id: 'g-auth', balance_after: 60 }),
      expect.objectContaining({ ai_stars: 42 }),
    )
  })

  it('shows wallet change after reconcile when current balance differs', async () => {
    readPendingStarsGrant.mockReturnValue({
      adminId: 'admin-1',
      recipientId: 'user-1',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      noteFingerprint: '0:0',
      idempotencyKey: 'grant-wallet-moved',
      createdAt: new Date().toISOString(),
    })
    fetchAdminStarsGrantByIdempotency.mockResolvedValue({
      outcome: 'recorded',
      message: 'Completed',
      grant: {
        grant_id: 'g-moved',
        recipient_id: 'user-1',
        actor_id: 'admin-1',
        amount: 50,
        balance_before: 10,
        balance_after: 60,
        reason: 'CUSTOMER_APPRECIATION',
        note: null,
        source: 'ADMIN_GRANT',
        status: 'completed',
        idempotency_key: 'grant-wallet-moved',
        created_at: null,
        idempotent_replay: true,
      },
      wallet: {
        recipient_id: 'user-1',
        ai_stars: 30,
        ai_stars_unlimited: false,
        ai_stars_iap_debt: 0,
      },
      wallet_mutations: 0,
    })
    render(
      <GrantStarsModal
        customer={customer}
        adminId="admin-1"
        onClose={vi.fn()}
        onGranted={vi.fn()}
      />,
    )
    await screen.findByText(/Wallet has changed since the grant completed/i)
    expect(postAdminStarsGrant).not.toHaveBeenCalled()
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
