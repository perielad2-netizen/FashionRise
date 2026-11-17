import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { LegalConsentField } from './LegalConsentField'

function Harness() {
  const [checked, setChecked] = useState(false)
  return (
    <LegalConsentField
      checked={checked}
      onCheckedChange={setChecked}
      shortLabel="I confirm short consent."
      intro="By doing this, I confirm that:"
      points={['Point one about rights.', 'Point two about privacy.']}
      checkboxTestId="legal-consent-box"
      termsTestId="legal-consent-terms"
      expandedExtra={<a href="/privacy">Privacy Policy</a>}
    />
  )
}

describe('LegalConsentField', () => {
  it('starts unchecked and expands full terms without checking', () => {
    render(<Harness />)
    const box = screen.getByTestId('legal-consent-box')
    expect(box).not.toBeChecked()
    expect(screen.queryByTestId('legal-consent-terms')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Read full terms/i }))
    expect(screen.getByTestId('legal-consent-terms')).toBeTruthy()
    expect(screen.getByText(/Point one about rights/i)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Privacy Policy/i })).toBeTruthy()
    expect(box).not.toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: /Hide full terms/i }))
    expect(screen.queryByTestId('legal-consent-terms')).toBeNull()
  })

  it('checks only when the checkbox is used', () => {
    const onChange = vi.fn()
    render(
      <LegalConsentField
        checked={false}
        onCheckedChange={onChange}
        shortLabel="I confirm short consent."
        intro="Intro"
        points={['One']}
        checkboxTestId="legal-consent-box"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Read full terms/i }))
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('legal-consent-box'))
    expect(onChange).toHaveBeenCalledWith(true)
  })
})
