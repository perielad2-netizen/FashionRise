import { ApiError } from '@/services/api/client'

/**
 * Map register API failures to actionable product copy.
 * Prefer distinct invitation outcomes (expired / used / email mismatch / gate off)
 * over a single generic 403 string.
 */
export function mapRegisterError(err: ApiError): string {
  if (err.status === 0) {
    return 'Unable to reach FashionRise. Check that the API is running.'
  }

  if (err.status === 403) {
    const msg = (err.message || '').trim()
    const lower = msg.toLowerCase()
    if (lower.includes('expired')) {
      return 'This invitation has expired. Ask the operator for a new invite.'
    }
    if (lower.includes('already been used')) {
      return 'This invitation has already been used. Sign in if you already created an account.'
    }
    if (lower.includes('does not match')) {
      return 'This invitation is for a different email. Use the invited address, or ask for a new invite.'
    }
    if (lower.includes('not available')) {
      return 'Account creation is not available right now. Try signing in, or contact the operator.'
    }
    if (msg) {
      return `${msg}. Ask the operator for a new invite, or sign in if you already have an account.`
    }
    return 'This invitation is not valid. Ask the operator for a new invite, or sign in if you already created an account.'
  }

  if (err.status === 409) {
    return err.message || 'An account with this email or username already exists. Try signing in.'
  }

  if (err.status === 422) {
    return err.message || 'Please check your details and try again.'
  }

  if (err.status >= 500) {
    return 'FashionRise is temporarily unavailable. If this continues, try signing in — your account may already exist.'
  }

  return err.message || 'Unable to create your account. Please try again.'
}
