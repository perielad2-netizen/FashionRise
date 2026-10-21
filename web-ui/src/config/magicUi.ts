/**
 * Frontend Magic UX gate.
 *
 * Default off so production builds keep Magic as “Soon” until a separately
 * approved activation (backend worker + Nginx AI allowlist + this flag).
 * Does not authorize paid OpenAI calls by itself.
 */
export function isMagicUiEnabled(): boolean {
  const raw = (import.meta.env.VITE_MAGIC_UI_ENABLED as string | undefined)?.trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}
