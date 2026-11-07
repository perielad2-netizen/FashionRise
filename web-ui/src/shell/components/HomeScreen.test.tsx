import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HomeScreen } from './HomeScreen'

vi.mock('@/config/myCroquisUi', () => ({
  isMyCroquisUiEnabled: () => true,
}))

describe('HomeScreen', () => {
  it('shows FashionRise brand and routes destinations', () => {
    const onNavigate = vi.fn()
    render(<HomeScreen username="Maya Designer" onNavigate={onNavigate} />)

    expect(screen.getByRole('heading', { level: 1, name: /FashionRise/i })).toBeInTheDocument()
    expect(screen.getByText(/Welcome back, Maya/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Start creating/i }))
    expect(onNavigate).toHaveBeenCalledWith('create')

    const destinations = screen.getByRole('navigation', { name: 'Studio destinations' })
    fireEvent.click(within(destinations).getByRole('button', { name: /My Designs/i }))
    expect(onNavigate).toHaveBeenCalledWith('designs')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Looks/i }))
    expect(onNavigate).toHaveBeenCalledWith('looks')
    fireEvent.click(within(destinations).getByRole('button', { name: /My Models/i }))
    expect(onNavigate).toHaveBeenCalledWith('croquis')
  })
})
