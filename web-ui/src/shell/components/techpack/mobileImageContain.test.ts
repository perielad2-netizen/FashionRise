/** Contract: Magic look frames must use object-fit: contain (never cover). */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const componentsDir = path.resolve(__dirname, '..')

describe('Create Real Design Magic image contain', () => {
  it('hero and waiting-modal thumb use contain + cream letterbox', () => {
    const hero = readFileSync(path.join(componentsDir, 'TechpackScreen.module.css'), 'utf8')
    const overlay = readFileSync(
      path.join(componentsDir, 'techpack/GenerateAiPdfOverlay.module.css'),
      'utf8',
    )

    const heroBlock = hero.slice(hero.indexOf('.heroImage'), hero.indexOf('.heroPlaceholder'))
    expect(heroBlock).toMatch(/object-fit:\s*contain/)
    expect(heroBlock).not.toMatch(/object-fit:\s*cover/)
    expect(heroBlock).toMatch(/object-position:\s*center/)

    const heroVisual = hero.slice(hero.indexOf('.heroVisual'), hero.indexOf('.heroImage'))
    expect(heroVisual).toMatch(/aspect-ratio:\s*3\s*\/\s*4/)
    expect(heroVisual).toMatch(/#faf6f1|#f3ebe3/)

    const thumbBlock = overlay.slice(overlay.indexOf('.thumb,'), overlay.indexOf('.spinner'))
    expect(thumbBlock).toMatch(/object-fit:\s*contain/)
    expect(thumbBlock).not.toMatch(/object-fit:\s*cover/)
    expect(thumbBlock).toMatch(/#faf6f1|#f3ebe3/)

    const spinnerBlock = overlay.slice(overlay.indexOf('.spinner'), overlay.indexOf('@keyframes'))
    expect(spinnerBlock).toMatch(/position:\s*relative/)
    expect(spinnerBlock).not.toMatch(/position:\s*absolute/)
  })
})
