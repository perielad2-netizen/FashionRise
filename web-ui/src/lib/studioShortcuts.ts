export type StudioShortcut = 'draw' | 'erase' | 'undo' | 'redo'

type ShortcutEvent = {
  key: string
  metaKey: boolean
  ctrlKey: boolean
  shiftKey: boolean
  altKey: boolean
  target: EventTarget | null
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
}

/** Beta shortcuts advertised in Settings. Ignores keys typed into fields. */
export function matchStudioShortcut(event: ShortcutEvent): StudioShortcut | null {
  if (event.altKey || isTypingTarget(event.target)) return null
  const key = event.key.toLowerCase()
  const mod = event.metaKey || event.ctrlKey
  if (mod && key === 'z') return event.shiftKey ? 'redo' : 'undo'
  if (mod && key === 'y' && !event.shiftKey) return 'redo'
  if (mod) return null
  if (key === 'b') return 'draw'
  if (key === 'e') return 'erase'
  return null
}
