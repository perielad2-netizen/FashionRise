/**
 * WEB-V4J Stage D: Front/Back Studio (client-only until flag + assets ship).
 *
 * Default off — production behavior stays single-sided draft v1.
 */
export function isStudioFrontBackEnabled(): boolean {
  const raw = (import.meta.env.VITE_STUDIO_FRONT_BACK_ENABLED as string | undefined)?.trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
