import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import {
  BUILTIN_MODELS,
  canvasSrcForModel,
  modelHasRearAsset,
  type SelectableBuiltinModelId,
} from '@/assets/modelLibrary'
import { REAR_CROQUIS_PUBLISHED, isRearCroquisPublished } from '@/assets/rearCroquisPublished'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'

const LIBRARY_DIR = resolve(__dirname, '../../public/models/library')

const APPROVED_BACK_IDS: readonly SelectableBuiltinModelId[] = [
  'female-straight',
  'female-hand-hip',
  'female-contrapposto',
  'female-cross-ankle',
  'female-cross-leg',
  'male-straight',
  'male-step',
  'male-walk',
  'male-contrapposto',
] as const

/** Read PNG IHDR width/height without extra deps. */
function pngSize(buf: Buffer): { width: number; height: number } {
  expect(buf.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
}

function libraryFile(name: string): Buffer {
  const path = resolve(LIBRARY_DIR, name)
  expect(existsSync(path), `missing ${path}`).toBe(true)
  return readFileSync(path)
}

describe('operator PAIRS_09 rear croquis assets', () => {
  it('keeps the production Front/Back feature flag OFF by default', () => {
    expect(isStudioFrontBackEnabled()).toBe(false)
  })

  it('publishes exactly the nine approved backs and leaves female-atelier unavailable', () => {
    for (const id of APPROVED_BACK_IDS) {
      expect(REAR_CROQUIS_PUBLISHED[id], id).toBe(true)
      expect(isRearCroquisPublished(id)).toBe(true)
      expect(modelHasRearAsset(id)).toBe(true)
    }
    expect(REAR_CROQUIS_PUBLISHED['female-atelier']).toBe(false)
    expect(isRearCroquisPublished('female-atelier')).toBe(false)
    expect(modelHasRearAsset('female-atelier')).toBe(false)
    expect(canvasSrcForModel('female-atelier', 'back')).toBe('/models/library/female-atelier-back.png')
    expect(existsSync(resolve(LIBRARY_DIR, 'female-atelier-back.png'))).toBe(false)
  })

  it('installs nine rear PNGs that match each model id and front canvas size', () => {
    const seenSha = new Set<string>()
    for (const id of APPROVED_BACK_IDS) {
      const frontName = `${id}.png`
      const backName = `${id}-back.png`
      expect(canvasSrcForModel(id, 'front')).toBe(`/models/library/${frontName}`)
      expect(canvasSrcForModel(id, 'back')).toBe(`/models/library/${backName}`)

      const front = libraryFile(frontName)
      const back = libraryFile(backName)
      const frontSize = pngSize(front)
      const backSize = pngSize(back)
      expect(backSize, id).toEqual(frontSize)

      const frontSha = createHash('sha256').update(front).digest('hex')
      const backSha = createHash('sha256').update(back).digest('hex')
      expect(backSha, `${id} must not equal its front`).not.toBe(frontSha)
      expect(seenSha.has(backSha), `${id} back must be unique`).toBe(false)
      seenSha.add(backSha)

      // RGBA PNG signature already checked; require non-trivial file.
      expect(back.byteLength).toBeGreaterThan(20_000)
    }
    expect(seenSha.size).toBe(9)
  })

  it('does not map any model onto another model’s rear asset bytes', () => {
    const bySha = new Map<string, string>()
    for (const id of APPROVED_BACK_IDS) {
      const sha = createHash('sha256').update(libraryFile(`${id}-back.png`)).digest('hex')
      const prior = bySha.get(sha)
      expect(prior, `duplicate rear bytes: ${prior} vs ${id}`).toBeUndefined()
      bySha.set(sha, id)
    }
  })

  it('keeps library front masters distinct from installed backs for every selectable', () => {
    for (const model of BUILTIN_MODELS) {
      const front = libraryFile(`${model.id}.png`)
      const frontSha = createHash('sha256').update(front).digest('hex')
      if (!REAR_CROQUIS_PUBLISHED[model.id]) {
        expect(existsSync(resolve(LIBRARY_DIR, `${model.id}-back.png`))).toBe(false)
        continue
      }
      const backSha = createHash('sha256').update(libraryFile(`${model.id}-back.png`)).digest('hex')
      expect(backSha).not.toBe(frontSha)
    }
  })
})
