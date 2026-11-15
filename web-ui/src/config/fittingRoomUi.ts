/**
 * AI Fitting Room UI gate.
 *
 * PM-approved default ON. Set VITE_FITTING_ROOM_UI_ENABLED=false to hide
 * for a tip/build. Independent of Studio Magic / Try On Person / My Croquis.
 * Does not enable Wardrobe, Stylist, shopping, or new billing.
 */
export function isFittingRoomUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_FITTING_ROOM_UI_ENABLED as string | undefined)
    ?.trim()
    .toLowerCase()
  if (raw == null || raw === '') return true
  if (raw === '0' || raw === 'false' || raw === 'no' || raw === 'off') return false
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
