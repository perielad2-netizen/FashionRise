import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

describe('DetailsEditorSheet responsive layout CSS', () => {
  const css = readFileSync(path.join(__dirname, 'DetailsEditorSheet.module.css'), 'utf8')

  it('defines tablet and desktop breakpoints with wider sheet + sidebar', () => {
    expect(css).toMatch(/@media \(min-width:\s*641px\)/)
    expect(css).toMatch(/@media \(min-width:\s*1024px\)/)
    expect(css).toMatch(/grid-template-columns:\s*280px/)
    expect(css).toMatch(/\.sidebar/)
    expect(css).toMatch(/min\(1120px/)
    expect(css).toMatch(/object-fit:\s*contain/)
    expect(css).toMatch(/\.footerStack/)
    expect(css).toMatch(/\.doneBtn/)
    // Chips wrap — no exclusive horizontal overflow strategy for chips
    expect(css).toMatch(/\.chipRow[\s\S]*flex-wrap:\s*wrap/)
  })
})
