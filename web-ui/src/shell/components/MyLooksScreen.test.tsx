import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MyLooksScreen } from '@/shell/components/MyLooksScreen'
import type { LookRecord } from '@/services/looksApi'

const listLooks = vi.fn()
const updateLook = vi.fn()
const deleteLook = vi.fn()
const fetchJobImageBlob = vi.fn()

vi.mock('@/services/looksApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/looksApi')>()
  return {
    ...actual,
    listLooks: (...args: unknown[]) => listLooks(...args),
    updateLook: (...args: unknown[]) => updateLook(...args),
    deleteLook: (...args: unknown[]) => deleteLook(...args),
  }
})

vi.mock('@/services/ai/magicApi', () => ({
  fetchJobImageBlob: (...args: unknown[]) => fetchJobImageBlob(...args),
}))

const LOOK_A: LookRecord = {
  id: 'look-a',
  title: 'Blush gown',
  is_favorite: false,
  is_archived: false,
  kind: 'single',
  created_at: '2026-10-26T12:00:00Z',
  updated_at: '2026-10-26T12:00:00Z',
  front: {
    job_id: 'job-a',
    studio_side: 'front',
    has_image: true,
    summary: 'A soft blush evening look',
    created_at: '2026-10-26T12:00:00Z',
  },
  back: null,
  design_id: null,
  magic_operation_id: null,
}

const LOOK_DUAL: LookRecord = {
  id: 'op-dual',
  title: 'Dual runway',
  is_favorite: true,
  is_archived: false,
  kind: 'dual',
  created_at: '2026-10-26T13:00:00Z',
  updated_at: '2026-10-26T13:00:00Z',
  front: {
    job_id: 'jf',
    studio_side: 'front',
    has_image: true,
    summary: 'Front notes',
    created_at: '2026-10-26T13:00:00Z',
  },
  back: {
    job_id: 'jb',
    studio_side: 'back',
    has_image: true,
    summary: 'Back notes',
    created_at: '2026-10-26T13:01:00Z',
  },
  design_id: null,
  magic_operation_id: 'op-dual',
}

describe('MyLooksScreen', () => {
  beforeEach(() => {
    listLooks.mockReset()
    updateLook.mockReset()
    deleteLook.mockReset()
    fetchJobImageBlob.mockReset()
    fetchJobImageBlob.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }))
    // IntersectionObserver may be missing / inert in jsdom — treat as immediately visible.
    // @ts-expect-error test polyfill
    window.IntersectionObserver = class {
      private cb: IntersectionObserverCallback
      constructor(cb: IntersectionObserverCallback) {
        this.cb = cb
      }
      observe(target: Element) {
        this.cb(
          [{ isIntersecting: true, target } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        )
      }
      disconnect() {
        /* noop */
      }
      unobserve() {
        /* noop */
      }
    }
  })

  it('renders gallery cards with Front/Back badges and opens details', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_DUAL, LOOK_A], total: 2, limit: 24, offset: 0 })
    render(<MyLooksScreen onBackToStudio={() => undefined} />)

    expect(screen.getByRole('heading', { level: 1, name: 'My Looks' })).toBeInTheDocument()
    const gallery = await screen.findByRole('list', { name: 'My Looks gallery' })
    const dualCard = within(gallery).getByText('Dual runway').closest('li')
    expect(dualCard).toBeTruthy()
    expect(within(dualCard as HTMLElement).getByText('Front')).toBeInTheDocument()
    expect(within(dualCard as HTMLElement).getByText('Back')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'View details for Dual runway' }))
    expect(await screen.findByRole('dialog', { name: 'Dual runway' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download front' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download back' })).toBeInTheDocument()
  })

  it('favorites and archives from the detail dialog', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_A], total: 1, limit: 24, offset: 0 })
    updateLook
      .mockResolvedValueOnce({ ...LOOK_A, is_favorite: true })
      .mockResolvedValueOnce({ ...LOOK_A, is_favorite: true, is_archived: true })

    render(<MyLooksScreen onBackToStudio={() => undefined} />)
    await screen.findByText('Blush gown')
    fireEvent.click(screen.getByRole('button', { name: 'View details for Blush gown' }))

    fireEvent.click(screen.getByRole('button', { name: 'Favorite' }))
    await waitFor(() => expect(updateLook).toHaveBeenCalledWith('look-a', { is_favorite: true }))

    fireEvent.click(screen.getByRole('button', { name: 'Archive' }))
    await waitFor(() => expect(updateLook).toHaveBeenCalledWith('look-a', { is_archived: true }))
  })

  it('shows empty and error states', async () => {
    listLooks.mockResolvedValueOnce({ items: [], total: 0, limit: 24, offset: 0 })
    const { rerender } = render(<MyLooksScreen onBackToStudio={() => undefined} />)
    expect(await screen.findByText(/No looks here yet/)).toBeInTheDocument()

    listLooks.mockRejectedValueOnce(new Error('offline'))
    rerender(<MyLooksScreen onBackToStudio={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('offline')
  })

  it('filters favorites via toolbar', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_DUAL], total: 1, limit: 24, offset: 0 })
    render(<MyLooksScreen onBackToStudio={() => undefined} />)
    await screen.findByText('Dual runway')
    fireEvent.click(screen.getByRole('tab', { name: 'Favorites' }))
    await waitFor(() =>
      expect(listLooks).toHaveBeenCalledWith(
        expect.objectContaining({ filter: 'favorites' }),
      ),
    )
  })

  it('cancels delete confirmation without calling the API', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_A], total: 1, limit: 24, offset: 0 })
    render(<MyLooksScreen onBackToStudio={() => undefined} />)
    await screen.findByText('Blush gown')
    fireEvent.click(screen.getByRole('button', { name: 'Delete Blush gown' }))
    expect(screen.getByRole('dialog', { name: /Delete “Blush gown”/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog', { name: /Delete “Blush gown”/ })).toBeNull()
    expect(deleteLook).not.toHaveBeenCalled()
    expect(screen.getByText('Blush gown')).toBeInTheDocument()
  })

  it('deletes a look after confirm and removes the card', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_A, LOOK_DUAL], total: 2, limit: 24, offset: 0 })
    deleteLook.mockResolvedValue({ ok: true, alreadyGone: false })
    render(<MyLooksScreen onBackToStudio={() => undefined} />)
    await screen.findByText('Blush gown')
    fireEvent.click(screen.getByRole('button', { name: 'Delete Blush gown' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
    await waitFor(() => expect(deleteLook).toHaveBeenCalledWith('look-a'))
    expect(screen.queryByText('Blush gown')).toBeNull()
    expect(screen.getByText('Dual runway')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('permanently deleted')
  })

  it('offers retry when delete fails without claiming success', async () => {
    listLooks.mockResolvedValue({ items: [LOOK_A], total: 1, limit: 24, offset: 0 })
    deleteLook.mockResolvedValue({
      ok: false,
      error: 'Still present',
      outcomeUncertain: false,
      canRetry: true,
    })
    render(<MyLooksScreen onBackToStudio={() => undefined} />)
    await screen.findByText('Blush gown')
    fireEvent.click(screen.getByRole('button', { name: 'Delete Blush gown' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Still present')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByText('Blush gown')).toBeInTheDocument()
  })
})
