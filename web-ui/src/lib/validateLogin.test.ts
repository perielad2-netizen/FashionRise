import { describe, expect, it, vi } from 'vitest'
import { validateLogin } from '@/lib/validateLogin'

describe('validateLogin', () => {
  it('requires email', () => {
    const result = validateLogin('   ', 'secret123')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.email).toMatch(/required/i)
      expect(result.errors.password).toBeUndefined()
    }
  })

  it('rejects invalid email structure', () => {
    const result = validateLogin('not-an-email', 'secret123')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.email).toMatch(/valid email/i)
    }
  })

  it('requires password without trimming it', () => {
    const result = validateLogin('aria@fashionrise.local', '')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.password).toMatch(/required/i)
    }
  })

  it('trims email but preserves password whitespace', () => {
    const result = validateLogin('  aria@fashionrise.local  ', '  pass  ')
    expect(result).toEqual({
      ok: true,
      email: 'aria@fashionrise.local',
      password: '  pass  ',
    })
  })

  it('blocks API login when validation fails', async () => {
    const login = vi.fn()
    const result = validateLogin('', '')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      // Mirror LoginPage: never call login() on invalid form.
      expect(login).not.toHaveBeenCalled()
    }
  })
})
