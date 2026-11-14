/**
 * AI Fitting Room UI gate (parallel track vs Android QA).
 *
 * Fail closed — production / Android tip builds must keep this OFF until PM
 * approval. Independent of Studio Magic / Try On Person / My Croquis gates.
 * Does not enable Wardrobe, Stylist, shopping, or new billing.
 */
export function isFittingRoomUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_FITTING_ROOM_UI_ENABLED as string | undefined)
    ?.trim()
    .toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
