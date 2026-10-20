export type RegisterFieldErrors = {
  email?: string
  username?: string
  displayName?: string
  password?: string
  confirmPassword?: string
  invitationCode?: string
}

export type ValidatedRegister = {
  ok: true
  email: string
  username: string
  displayName: string | null
  password: string
  invitationCode: string
}

export type RegisterValidationResult =
  | ValidatedRegister
  | { ok: false; errors: RegisterFieldErrors }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const USERNAME_RE = /^[a-zA-Z0-9_]{2,64}$/

export function validateRegister(input: {
  email: string
  username: string
  displayName: string
  password: string
  confirmPassword: string
  invitationCode: string
}): RegisterValidationResult {
  const errors: RegisterFieldErrors = {}
  const email = input.email.trim().toLowerCase()
  const username = input.username.trim()
  const displayNameRaw = input.displayName.trim()
  const invitationCode = input.invitationCode.trim()
  // Passwords are not trimmed beyond what the backend login path does; keep exact body.
  const password = input.password
  const confirmPassword = input.confirmPassword

  if (!email) errors.email = 'Enter your email.'
  else if (!EMAIL_RE.test(email)) errors.email = 'Enter a valid email address.'

  if (!username) errors.username = 'Choose a username.'
  else if (username.length < 2 || username.length > 64)
    errors.username = 'Username must be 2–64 characters.'
  else if (!USERNAME_RE.test(username))
    errors.username = 'Use letters, numbers, and underscores only.'

  if (displayNameRaw.length > 120) errors.displayName = 'Display name must be at most 120 characters.'

  if (!password) errors.password = 'Enter a password.'
  else if (password.length < 8) errors.password = 'Password must be at least 8 characters.'
  else if (password.length > 128) errors.password = 'Password must be at most 128 characters.'

  if (!confirmPassword) errors.confirmPassword = 'Confirm your password.'
  else if (confirmPassword !== password) errors.confirmPassword = 'Passwords do not match.'

  if (!invitationCode) errors.invitationCode = 'Enter your invitation code.'
  else if (invitationCode.length < 16)
    errors.invitationCode = 'Invitation code looks incomplete.'

  if (Object.keys(errors).length > 0) return { ok: false, errors }

  return {
    ok: true,
    email,
    username,
    displayName: displayNameRaw ? displayNameRaw : null,
    password,
    invitationCode,
  }
}
