/**
 * V2-0034 — personal (My Model) is FRONT-only in Studio.
 * Source regressions so we do not reintroduce Back display while personal is pinned.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = readFileSync(resolve(__dirname, 'useStudioEditor.ts'), 'utf8')
const SIDES = readFileSync(resolve(__dirname, 'studioEditorSides.ts'), 'utf8')

describe('useStudioEditor personal FRONT-only (V2-0034)', () => {
  it('canOpenBackPaper rejects personal', () => {
    expect(SIDES).toMatch(/if \(model === 'personal'\) return false/)
  })

  it('applyPersonalCroquisPin always commits activeSide front', () => {
    expect(SRC).toMatch(/V2-0034: personal is FRONT-only/)
    expect(SRC).toMatch(/setActiveSide\('front'\)/)
    // Both clear and keep paths must pin Front — no canOpenBackPaper('personal') branch.
    expect(SRC).not.toMatch(/canOpenBackPaper\('personal'\)/)
    const pinFn = SRC.slice(SRC.indexOf('const applyPersonalCroquisPin'))
    const body = pinFn.slice(0, pinFn.indexOf('requestPersonalCroquisPin'))
    expect(body).toMatch(/activeSide: 'front'/)
    expect(body.match(/activeSide: 'front'/g)?.length ?? 0).toBeGreaterThanOrEqual(2)
  })

  it('applyDocument coerces personal Back drafts to Front without clearing bags', () => {
    expect(SRC).toMatch(/displaySideForModel\(doc\.model, sides\.activeSide\)/)
    expect(SRC).toMatch(/without wiping preserved Back artwork/)
    expect(SRC).toMatch(/authoritativeDocRef\.current = \{ \.\.\.doc, activeSide: viewSide \}/)
  })

  it('changeActiveSide still blocks Back when canOpenBackPaper is false', () => {
    expect(SRC).toMatch(/if \(side === 'back' && !canOpenBackPaper\(model\)\) return/)
  })
})
