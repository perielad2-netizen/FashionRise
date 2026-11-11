/**
 * Frontend registration UX gates.
 *
 * Backend `/auth/registration/status` is authoritative for whether Create Account
 * is offered. `VITE_REGISTRATION_UI_ENABLED` remains a build-time fail-closed
 * overlay for staged FE releases that must not advertise registration even when
 * the API later opens (legacy invite activation path). Prefer backend status for
 * App Store public registration so activation can flip API mode without a Vite rebuild.
 */
export function isRegistrationUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_REGISTRATION_UI_ENABLED as string | undefined)?.trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}

/**
 * Whether the SPA may advertise /register.
 * Backend availability wins; the Vite flag can additionally force-enable in local
 * builds when the status endpoint is mocked. Production builds keep Vite false and
 * rely on the live status payload.
 */
export function canAdvertiseRegistration(statusAvailable: boolean | null | undefined): boolean {
  if (statusAvailable === true) return true
  if (statusAvailable === false) return false
  // Status unknown (failed fetch): only show when the build-time flag is on.
  return isRegistrationUiEnabled()
}
