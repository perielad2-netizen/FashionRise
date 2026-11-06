/**
 * Create My Croquis wizard UI gate.
 *
 * Independent of Studio FRONT_BACK / MAGIC / DUAL / REGISTRATION (#136).
 * Default OFF — production builds must not show the wizard until a separately
 * authorized FE activation. Does not enable upload or AI gates.
 */
export function isMyCroquisUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_MY_CROQUIS_UI_ENABLED as string | undefined)
    ?.trim()
    .toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
