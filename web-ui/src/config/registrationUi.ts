/**
 * Frontend registration UX gate.
 *
 * Backend `REGISTRATION_ENABLED` remains the authoritative signup gate.
 * This flag only controls whether the SPA advertises Create Account / /register.
 * Keep false in production until the separately approved WEB-V3B activation
 * (migration 004 + Nginx allowlist + invitations).
 */
export function isRegistrationUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_REGISTRATION_UI_ENABLED as string | undefined)?.trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
