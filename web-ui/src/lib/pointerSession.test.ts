import { describe, expect, it } from 'vitest'
import { decidePointer, pressureForPointer, type DrawSession } from '@/lib/pointerSession'

const idle: DrawSession = { drawing: false, activePointerId: null }
const active: DrawSession = { drawing: true, activePointerId: 7 }

describe('decidePointer', () => {
  it('does not continue a mouse stroke when the primary button is up', () => {
    expect(
      decidePointer(active, {
        type: 'move',
        pointerId: 7,
        pointerType: 'mouse',
        button: 0,
        buttons: 0,
      }),
    ).toBe('end')
  })

  it('continues a mouse stroke while the primary button is held', () => {
    expect(
      decidePointer(active, {
        type: 'move',
        pointerId: 7,
        pointerType: 'mouse',
        button: 0,
        buttons: 1,
      }),
    ).toBe('append')
  })

  it('ends on pointerup and pointercancel', () => {
    expect(
      decidePointer(active, {
        type: 'up',
        pointerId: 7,
        pointerType: 'mouse',
        button: 0,
        buttons: 0,
      }),
    ).toBe('end')
    expect(
      decidePointer(active, {
        type: 'cancel',
        pointerId: 7,
        pointerType: 'pen',
        button: 0,
        buttons: 0,
      }),
    ).toBe('end')
  })

  it('ignores a different pointer id while a stroke is active', () => {
    expect(
      decidePointer(active, {
        type: 'move',
        pointerId: 9,
        pointerType: 'mouse',
        button: 0,
        buttons: 1,
      }),
    ).toBe('ignore')
    expect(
      decidePointer(active, {
        type: 'up',
        pointerId: 3,
        pointerType: 'touch',
        button: 0,
        buttons: 1,
      }),
    ).toBe('ignore')
  })

  it('does not begin a stroke from the secondary mouse button', () => {
    expect(
      decidePointer(idle, {
        type: 'down',
        pointerId: 1,
        pointerType: 'mouse',
        button: 2,
        buttons: 2,
      }),
    ).toBe('ignore')
    expect(
      decidePointer(idle, {
        type: 'down',
        pointerId: 1,
        pointerType: 'mouse',
        button: 0,
        buttons: 1,
      }),
    ).toBe('begin')
  })
})

describe('pressureForPointer', () => {
  it('keeps pen pressure and defaults mouse', () => {
    expect(pressureForPointer('pen', 0.82)).toBe(0.82)
    expect(pressureForPointer('mouse', 0)).toBe(0.5)
  })
})
