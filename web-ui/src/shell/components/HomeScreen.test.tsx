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
  it('shows sketch→AI look hero and routes destinations without a logo plate', () => {
    const onNavigate = vi.fn()
    render(<HomeScreen username="Maya Designer" onNavigate={onNavigate} />)

    expect(screen.getByRole('heading', { level: 1, name: /Sketch it\. See it come to life\./i })).toBeInTheDocument()
    expect(screen.getByText(/Welcome back, Maya/i)).toBeInTheDocument()
    expect(screen.getByText('Fashion')).toBeInTheDocument()
    expect(screen.getByText('Rise')).toBeInTheDocument()
    expect(screen.getByText(/Turn your fashion ideas into stunning AI creations/i)).toBeInTheDocument()
    expect(screen.getByTestId('home-before-after-gallery')).toBeInTheDocument()
    expect(
      screen.getByTestId('home-gallery-composite-pink-gown-sketch-to-look'),
    ).toBeInTheDocument()
    expect(screen.getByAltText(/One FashionRise hero/i)).toBeInTheDocument()
    expect(document.querySelector('img[src*="fashion_rise_login"]')).toBeNull()
    expect(document.querySelectorAll('[data-testid="home-before-after-gallery"] img')).toHaveLength(
      1,
    )

    const cta = screen.getByTestId('home-start-creating')
    expect(cta).toHaveAccessibleName(/Start creating/i)
    fireEvent.click(cta)
    expect(onNavigate).toHaveBeenCalledWith('create')

    const destinations = screen.getByRole('navigation', { name: 'Studio destinations' })
    expect(within(destinations).queryByRole('button', { name: /^Create\b/i })).toBeNull()
    fireEvent.click(within(destinations).getByRole('button', { name: /My Designs/i }))
    expect(onNavigate).toHaveBeenCalledWith('designs')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Looks/i }))
    expect(onNavigate).toHaveBeenCalledWith('looks')
    fireEvent.click(within(destinations).getByRole('button', { name: /^Runway/i }))
    expect(onNavigate).toHaveBeenCalledWith('runway')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Models/i }))
    expect(onNavigate).toHaveBeenCalledWith('croquis')
  })

  it('keeps Start creating when authorized examples are overridden', () => {
    const onNavigate = vi.fn()
    render(
      <HomeScreen
        username="Maya Designer"
        onNavigate={onNavigate}
        homeExamples={[fixturePair]}
      />,
    )

    expect(screen.getByTestId('home-start-creating')).toBeInTheDocument()
    expect(screen.getByTestId('home-before-after-gallery')).toBeInTheDocument()
    expect(screen.getByAltText('Fixture sketch')).toBeInTheDocument()
    expect(screen.getByAltText('Fixture Magic look')).toBeInTheDocument()
  })
})
