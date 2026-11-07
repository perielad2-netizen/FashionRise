import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HomeScreen } from './HomeScreen'

vi.mock('@/config/myCroquisUi', () => ({
  isMyCroquisUiEnabled: () => true,
}))

describe('HomeScreen', () => {
  it('shows FashionRise logo brand and routes destinations', () => {
    const onNavigate = vi.fn()
    render(<HomeScreen username="Maya Designer" onNavigate={onNavigate} />)

    expect(screen.getByRole('heading', { level: 1, name: /FashionRise/i })).toBeInTheDocument()
    expect(screen.getByText(/Welcome back, Maya/i)).toBeInTheDocument()
    const logo = document.querySelector('img') as HTMLImageElement | null
    expect(logo?.getAttribute('src')).toContain('fashion_rise_login')
    expect(logo?.getAttribute('src') ?? '').not.toMatch(/model|croquis|female/i)

    fireEvent.click(screen.getByRole('button', { name: /Start creating/i }))
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
})
