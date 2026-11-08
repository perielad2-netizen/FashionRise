import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { PrivacyPolicyPage } from './PrivacyPolicyPage'
import { CONTACT_EMAIL } from '@/lib/contact'

describe('PrivacyPolicyPage', () => {
  it('renders public privacy content without requiring auth', () => {
    render(
      <MemoryRouter>
        <PrivacyPolicyPage />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('privacy-policy-page')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Account information/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Uploaded photos/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /AI processing/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Social Runway/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Stars and in-app purchases/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Data retention/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Your privacy rights/i })).toBeTruthy()
    expect(screen.getByRole('link', { name: CONTACT_EMAIL })).toHaveAttribute(
      'href',
      `mailto:${CONTACT_EMAIL}`,
    )
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})
