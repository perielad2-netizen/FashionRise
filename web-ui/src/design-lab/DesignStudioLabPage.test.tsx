import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DesignStudioLabPage } from '@/design-lab/DesignStudioLabPage'

describe('DesignStudioLabPage', () => {
  it('renders the visual prototype shell without claiming production Studio', () => {
    render(<DesignStudioLabPage />)
    expect(screen.getByText(/development prototype/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/creator workspace prototype/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /new design/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/model library/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/settings inspector prototype/i)).toBeInTheDocument()
  })
})
