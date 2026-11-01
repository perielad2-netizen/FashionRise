export type PointerPhase = 'down' | 'move' | 'up' | 'cancel'

export type PointerPhaseInput = {
  type: PointerPhase
  pointerId: number
  pointerType: string
  button: number
  buttons: number
}

export type DrawSession = {
  drawing: boolean
  activePointerId: number | null
}

export type PointerDecision = 'begin' | 'append' | 'end' | 'ignore'

/**
 * Single source of truth for pencil pointer lifecycle.
 * Mouse drawing continues only while the primary button is held.
 */
export function decidePointer(session: DrawSession, input: PointerPhaseInput): PointerDecision {
  if (input.type === 'down') {
    if (session.drawing) return 'ignore'
    if (input.pointerType === 'mouse' && input.button !== 0) return 'ignore'
    return 'begin'
  }

  if (!session.drawing) return 'ignore'
  if (session.activePointerId !== null && input.pointerId !== session.activePointerId) {
    return 'ignore'
  }

  if (input.type === 'up' || input.type === 'cancel') return 'end'

  // pointermove: a released mouse must not keep extending the stroke.
  if (input.pointerType === 'mouse' && (input.buttons & 1) === 0) return 'end'
  return 'append'
}

/** Pen/touch use real pressure when the device reports it. Mouse stays at a pencil default. */
export function pressureForPointer(pointerType: string, pressure: number): number {
  if ((pointerType === 'pen' || pointerType === 'touch') && pressure > 0 && pressure <= 1) {
    return pressure
  }
  return 0.5
}
