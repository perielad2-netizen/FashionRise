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

  it('shows Created with FashionRise caption and WhatsApp / Instagram / Facebook actions', () => {
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
    expect(screen.getByTestId('share-whatsapp')).toBeTruthy()
    expect(screen.getByTestId('share-instagram')).toBeTruthy()
    expect(screen.getByTestId('share-facebook')).toBeTruthy()
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

  it('opens Facebook sharer after preparing caption', async () => {
    render(<ShareSheet open onClose={() => undefined} payload={{ kind: 'look' }} />)
    fireEvent.click(screen.getByTestId('share-facebook'))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled()
      expect(window.open).toHaveBeenCalled()
    })
    const url = String(vi.mocked(window.open).mock.calls.at(-1)?.[0])
    expect(url).toContain('facebook.com/sharer')
    expect(url).toContain(encodeURIComponent(FASHIONRISE_PUBLIC_URL))
  })

  it('copies caption then opens Instagram', async () => {
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
    expect(copied).toContain('Created with FashionRise')
    expect(copied).toContain('Evening Gown')
    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('instagram.com'),
      '_blank',
      expect.any(String),
    )
  })
})
