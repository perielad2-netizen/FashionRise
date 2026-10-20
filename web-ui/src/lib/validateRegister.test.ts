import { describe, expect, it } from 'vitest'
import { validateRegister } from '@/lib/validateRegister'

const base = {
  email: 'invitee@example.com',
  username: 'invitee',
  displayName: '',
  password: 'StrongPass123!',
  confirmPassword: 'StrongPass123!',
  invitationCode: 'abcdefghijklmnopqrstuvwxyz012345',
}

describe('validateRegister', () => {
  it('accepts a complete valid form', () => {
    const result = validateRegister(base)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.email).toBe('invitee@example.com')
      expect(result.displayName).toBeNull()
    }
  })

  it('requires matching passwords', () => {
    const result = validateRegister({ ...base, confirmPassword: 'other' })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.confirmPassword).toBeTruthy()
  })

  it('requires invitation code', () => {
    const result = validateRegister({ ...base, invitationCode: '  ' })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.invitationCode).toBeTruthy()
  })

  it('rejects short passwords', () => {
    const result = validateRegister({
      ...base,
      password: 'short',
      confirmPassword: 'short',
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.password).toMatch(/8/)
  })

  it('rejects invalid usernames', () => {
    const result = validateRegister({ ...base, username: 'bad name!' })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.username).toBeTruthy()
  })
})
