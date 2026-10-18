export type LoginFieldErrors = {
  email?: string
  password?: string
}

export type LoginValidationResult =
  | { ok: true; email: string; password: string }
  | { ok: false; errors: LoginFieldErrors }

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Application-level login validation.
 * Trims email for the submitted value; password is left unchanged.
 */
export function validateLogin(email: string, password: string): LoginValidationResult {
  const trimmedEmail = email.trim()
  const errors: LoginFieldErrors = {}

  if (!trimmedEmail) {
    errors.email = 'Email is required.'
  } else if (!EMAIL_PATTERN.test(trimmedEmail)) {
    errors.email = 'Enter a valid email address.'
  }

  if (!password) {
    errors.password = 'Password is required.'
  }

  if (errors.email || errors.password) {
    return { ok: false, errors }
  }

  return { ok: true, email: trimmedEmail, password }
}
