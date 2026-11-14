import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AuthorizedHomeExample } from '@/shell/homeAuthorizedExamples'
import { HomeScreen } from './HomeScreen'

vi.mock('@/config/myCroquisUi', () => ({
  isMyCroquisUiEnabled: () => true,
}))

const fixturePair: AuthorizedHomeExample = {
  id: 'home-fixture',
  title: 'Authorized fixture',
  authorization: {
    source: 'PM unit-test fixture',
    licensedFor: 'home-marketing',
  },
  before: {
    src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"/>',
    alt: 'Fixture sketch',
    width: 60,
    height: 80,
  },
  after: {
    src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"/>',
    alt: 'Fixture Magic look',
    width: 60,
    height: 80,
  },
}

describe('HomeScreen', () => {
  it('shows FashionRise logo brand and routes destinations', () => {
    const onNavigate = vi.fn()
    render(<HomeScreen username="Maya Designer" onNavigate={onNavigate} />)

    expect(screen.getByRole('heading', { level: 1, name: /FashionRise/i })).toBeInTheDocument()
    expect(screen.getByText(/Welcome back, Maya/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Sketch a garment\. Turn it into a Magic look\./i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/generate an AI Magic look from your sketch/i),
    ).toBeInTheDocument()
    // Production catalog is empty — do not invent a misleading gallery.
    expect(screen.queryByTestId('home-before-after-gallery')).not.toBeInTheDocument()
    const logo = document.querySelector('img') as HTMLImageElement | null
    expect(logo?.getAttribute('src')).toContain('fashion_rise_login')
    expect(logo?.getAttribute('src') ?? '').not.toMatch(/model|croquis|female/i)

    const cta = screen.getByTestId('home-start-creating')
    expect(cta).toHaveAccessibleName(/Start creating/i)
    fireEvent.click(cta)
    expect(onNavigate).toHaveBeenCalledWith('create')

    const destinations = screen.getByRole('navigation', { name: 'Studio destinations' })
    fireEvent.click(within(destinations).getByRole('button', { name: /My Designs/i }))
    expect(onNavigate).toHaveBeenCalledWith('designs')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Looks/i }))
    expect(onNavigate).toHaveBeenCalledWith('looks')
    fireEvent.click(within(destinations).getByRole('button', { name: /^Runway/i }))
    expect(onNavigate).toHaveBeenCalledWith('runway')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Models/i }))
    expect(onNavigate).toHaveBeenCalledWith('croquis')
  })

  it('keeps branding and Start creating when authorized examples are present', () => {
    const onNavigate = vi.fn()
    render(
      <HomeScreen
        username="Maya Designer"
        onNavigate={onNavigate}
        homeExamples={[fixturePair]}
      />,
    )

    expect(screen.getByRole('heading', { level: 1, name: /FashionRise/i })).toBeInTheDocument()
    expect(screen.getByTestId('home-start-creating')).toBeInTheDocument()
    expect(screen.getByTestId('home-before-after-gallery')).toBeInTheDocument()
    expect(screen.getByAltText('Fixture sketch')).toBeInTheDocument()
    expect(screen.getByAltText('Fixture Magic look')).toBeInTheDocument()
  })
})
