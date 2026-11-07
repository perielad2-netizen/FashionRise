import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ShareSheet } from './ShareSheet'
import { FASHIONRISE_PUBLIC_URL } from '@/lib/sharePromo'

describe('ShareSheet', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
    // Force fallback sheet path (no Web Share API in jsdom by default).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (navigator as any).share
    vi.spyOn(window, 'open').mockImplementation(() => null)
  })

  it('shows Created with FashionRise caption and a single primary Share action', () => {
    render(
      <ShareSheet
        open
        onClose={() => undefined}
        payload={{ kind: 'look', title: 'Evening gown', imageUrl: 'blob:look' }}
      />,
    )
    expect(screen.getByTestId('share-sheet')).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Share your look/i })).toBeTruthy()
    expect(screen.getByTestId('share-caption').textContent).toContain('Created with FashionRise')
    expect(screen.getByTestId('share-caption').textContent).toContain('Search Google for FashionRise')
    expect(screen.getByTestId('share-primary')).toBeTruthy()
    expect(screen.queryByTestId('share-instagram')).toBeNull()
    expect(screen.queryByTestId('share-facebook')).toBeNull()
  })

  it('copies caption and saves image from the primary Share action', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['png'], { type: 'image/png' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <ShareSheet
        open
        onClose={() => undefined}
        payload={{ kind: 'look', title: 'Evening gown', imageUrl: 'blob:look' }}
      />,
    )
    fireEvent.click(screen.getByTestId('share-primary'))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled()
    })
    const copied = String(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0])
    expect(copied).toContain('Created with FashionRise')
    expect(copied).toContain(FASHIONRISE_PUBLIC_URL)
    expect(fetchMock).toHaveBeenCalled()
  })

  it('opens WhatsApp with encoded Created with FashionRise text', async () => {
    render(<ShareSheet open onClose={() => undefined} payload={{ kind: 'look' }} />)
    fireEvent.click(screen.getByTestId('share-whatsapp'))
    await waitFor(() => {
      expect(window.open).toHaveBeenCalled()
    })
    const url = String(vi.mocked(window.open).mock.calls[0][0])
    expect(url.startsWith('https://wa.me/?text=')).toBe(true)
    expect(decodeURIComponent(url.split('text=')[1])).toContain('Created with FashionRise')
  })
})
