import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = resolve(__dirname, '../..')

describe('Create Model canonical entry points', () => {
  it('My Models and Studio both import CreateModelWizard from the shared module', () => {
    const myModels = readFileSync(resolve(root, 'shell/components/MyCroquisScreen.tsx'), 'utf8')
    const studio = readFileSync(resolve(root, 'shell/components/CreatorWorkspace.tsx'), 'utf8')
    expect(myModels.includes("from '@/shell/createModel'")).toBe(true)
    expect(studio.includes("from '@/shell/createModel'")).toBe(true)
    expect(myModels.includes('entryPoint="my-models"')).toBe(true)
    expect(studio.includes('entryPoint="studio"')).toBe(true)
    expect(myModels.includes("from '@/shell/components/CreateMyCroquisWizard'")).toBe(false)
    expect(studio.includes("from '@/shell/components/CreateMyCroquisWizard'")).toBe(false)
  })

  it('shared barrel re-exports the single CreateMyCroquisWizard implementation', () => {
    const barrel = readFileSync(resolve(__dirname, 'index.ts'), 'utf8')
    expect(barrel.includes('CreateMyCroquisWizard as CreateModelWizard')).toBe(true)
    expect(barrel.includes('CreateMyCroquisWizard')).toBe(true)
  })

  it('upload preview uses a clipped DIV portrait card (not a button frame)', () => {
    const css = readFileSync(
      resolve(root, 'shell/components/CreateMyCroquisWizard.module.css'),
      'utf8',
    )
    const tsx = readFileSync(
      resolve(root, 'shell/components/CreateMyCroquisWizard.tsx'),
      'utf8',
    )
    expect(css.includes('.photoFrame')).toBe(true)
    expect(css.includes('overflow: hidden')).toBe(true)
    expect(css.includes('aspect-ratio: 3 / 4')).toBe(true)
    expect(css.includes('object-fit: contain')).toBe(true)
    expect(tsx.includes('create-model-photo-frame')).toBe(true)
    expect(tsx.includes('create-model-change-photo')).toBe(true)
    // Android WebView: do not host the preview <img> inside a clipping <button>.
    expect(tsx.includes('className={styles.photoHit}')).toBe(false)
  })
})
