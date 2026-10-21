import { describe, expect, it } from 'vitest'
import { ApiError } from '@/services/api/client'
import { mapRegisterError } from '@/lib/mapRegisterError'

describe('mapRegisterError', () => {
  it('surfaces expired invitations distinctly', () => {
    expect(mapRegisterError(new ApiError('Invitation has expired', 403, null))).toMatch(/expired/i)
  })

  it('surfaces used invitations distinctly', () => {
    expect(
      mapRegisterError(new ApiError('Invitation has already been used', 403, null)),
    ).toMatch(/already been used/i)
  })

  it('surfaces email mismatch distinctly', () => {
    expect(
      mapRegisterError(new ApiError('Invitation does not match this email', 403, null)),
    ).toMatch(/different email/i)
  })

  it('surfaces registration gate off distinctly', () => {
    expect(
      mapRegisterError(new ApiError('Registration is not available', 403, null)),
    ).toMatch(/not available/i)
  })

  it('keeps invalid-invite copy actionable', () => {
    expect(mapRegisterError(new ApiError('Invitation is not valid', 403, null))).toMatch(
      /invitation is not valid/i,
    )
  })

  it('prefers conflict message for existing accounts', () => {
    expect(mapRegisterError(new ApiError('Email already registered', 409, null))).toMatch(
      /email already registered/i,
    )
  })
})
