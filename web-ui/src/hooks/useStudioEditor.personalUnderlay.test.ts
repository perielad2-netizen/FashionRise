import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * #174 — Opening a My Designs save that reuses the active personal croquis pin
 * must still reload the underlay. applyDocument clears the object URL; without a
 * reload token in the effect deps, React skips the fetch when pin id/version are
 * unchanged and the canvas paints ink without croquis.
 */
describe('useStudioEditor personal underlay reload (#174)', () => {
  const source = readFileSync(resolve(__dirname, 'useStudioEditor.ts'), 'utf8')

  it('bumps personalUnderlayReloadToken inside applyDocument', () => {
    expect(source).toMatch(/setPersonalUnderlayReloadToken\(\(n\) => n \+ 1\)/)
  })

  it('includes personalUnderlayReloadToken in the personal underlay load effect deps', () => {
    expect(source).toMatch(
      /\[user\?\.id, model, personalCroquisId, personalCroquisVersion, personalUnderlayReloadToken\]/,
    )
  })
})
