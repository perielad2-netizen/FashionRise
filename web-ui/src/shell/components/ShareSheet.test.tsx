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
    vi.spyOn(window, 'open').mockImplementation(() => null)
  })

  it('shows promo caption and WhatsApp / Instagram / copy actions', () => {
    render(<ShareSheet open onClose={() => undefined} payload={{ kind: 'app' }} />)
    expect(screen.getByTestId('share-sheet')).toBeTruthy()
    expect(screen.getByTestId('share-caption').textContent).toContain(FASHIONRISE_PUBLIC_URL)
    expect(screen.getByTestId('share-whatsapp')).toBeTruthy()
    expect(screen.getByTestId('share-instagram')).toBeTruthy()
    expect(screen.getByTestId('share-copy-caption')).toBeTruthy()
  })

  it('opens WhatsApp with encoded promo text', () => {
    render(<ShareSheet open onClose={() => undefined} />)
    fireEvent.click(screen.getByTestId('share-whatsapp'))
    expect(window.open).toHaveBeenCalled()
    const url = String(vi.mocked(window.open).mock.calls[0][0])
    expect(url.startsWith('https://wa.me/?text=')).toBe(true)
    expect(decodeURIComponent(url.split('text=')[1])).toContain('FashionRise')
  })

  it('copies caption then opens Instagram profile', async () => {
    render(
      <ShareSheet
        open
        onClose={() => undefined}
        payload={{ kind: 'look', title: 'Evening Gown' }}
      />,
    )
    fireEvent.click(screen.getByTestId('share-instagram'))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled()
    })
    const copied = String(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0])
    expect(copied).toContain('Evening Gown')
    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('instagram.com'),
      '_blank',
      expect.any(String),
    )
  })

  it('copies the public app link', async () => {
    render(<ShareSheet open onClose={() => undefined} />)
    fireEvent.click(screen.getByTestId('share-copy-link'))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(FASHIONRISE_PUBLIC_URL)
    })
    expect(screen.getByTestId('share-flash').textContent).toMatch(/Link copied/i)
  })
})
