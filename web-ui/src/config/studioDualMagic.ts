/**
 * WEB-V4J Dual Magic (Front+Back polish) client gate.
 *
 * Default off — Front-only Magic stays available when Magic UI is on;
 * designs with Back ink show a coming-soon notice instead of enqueueing
 * unsupported /polish-dual (or Back-side) paid jobs until Dual Magic ships.
 */
export function isStudioDualMagicEnabled(): boolean {
  const raw = (import.meta.env.VITE_STUDIO_DUAL_MAGIC_ENABLED as string | undefined)?.trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
