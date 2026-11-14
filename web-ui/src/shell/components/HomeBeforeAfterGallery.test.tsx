import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import type { AuthorizedHomeExample } from '@/shell/homeAuthorizedExamples'
import { HomeBeforeAfterGallery } from './HomeBeforeAfterGallery'

const svg =
  'data:image/svg+xml,' +
  encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="90" height="120"/>')

function pair(id: string, title: string): AuthorizedHomeExample {
  return {
    id,
    title,
    authorization: {
      source: 'PM unit-test fixture',
      licensedFor: 'home-marketing',
    },
    before: { src: svg, alt: `${title} sketch`, width: 90, height: 120 },
    after: { src: svg, alt: `${title} Magic look`, width: 90, height: 120 },
  }
}

describe('HomeBeforeAfterGallery', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('prefers-reduced-motion'),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders nothing when the authorized catalog is empty', () => {
    const { container } = render(<HomeBeforeAfterGallery examples={[]} />)
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByTestId('home-before-after-gallery')).not.toBeInTheDocument()
  })

  it('renders authorized pairs with reserved image dimensions and lazy non-first slides', () => {
    render(<HomeBeforeAfterGallery examples={[pair('a', 'Look A'), pair('b', 'Look B')]} />)

    expect(screen.getByTestId('home-before-after-gallery')).toBeInTheDocument()
    expect(screen.getByText(/Sketch → AI look/i)).toBeInTheDocument()
    expect(screen.getByTestId('home-gallery-slide-a')).toBeInTheDocument()

    const firstBefore = screen.getByAltText('Look A sketch')
    expect(firstBefore).toHaveAttribute('width', '90')
    expect(firstBefore).toHaveAttribute('height', '120')
    expect(firstBefore.getAttribute('loading')).toBe('eager')

    const secondBefore = screen.getByAltText('Look B sketch')
    expect(secondBefore.getAttribute('loading')).toBe('lazy')
  })

  it('exposes touch-sized prev/next controls and marks reduced-motion preference', () => {
    render(<HomeBeforeAfterGallery examples={[pair('a', 'Look A'), pair('b', 'Look B')]} />)

    const gallery = screen.getByTestId('home-before-after-gallery')
    expect(gallery).toHaveAttribute('data-reduced-motion', 'true')

    const prev = screen.getByTestId('home-gallery-prev')
    const next = screen.getByTestId('home-gallery-next')
    expect(prev).toHaveAccessibleName(/Previous example/i)
    expect(next).toHaveAccessibleName(/Next example/i)

    fireEvent.click(next)
    expect(screen.getByTestId('home-gallery-dot-1')).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(prev)
    expect(screen.getByTestId('home-gallery-dot-0')).toHaveAttribute('aria-selected', 'true')
  })
})
