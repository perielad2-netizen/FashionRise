import { describe, expect, it } from 'vitest'
import {
  BUILTIN_MODELS,
  DEFAULT_FEMALE_MODEL,
  DEFAULT_MALE_MODEL,
  DEFAULT_MODEL,
  LEGACY_MODEL_CANVAS,
  canvasSrcForModel,
  defaultModelForGender,
  isLegacyModelId,
  isModelChoice,
  modelLabel,
  normalizeModelChoice,
} from '@/assets/modelLibrary'

describe('modelLibrary', () => {
  it('defaults new drawings to the approved straight-standing models', () => {
    expect(DEFAULT_MODEL).toBe('female-straight')
    expect(DEFAULT_FEMALE_MODEL).toBe('female-straight')
    expect(DEFAULT_MALE_MODEL).toBe('male-straight')
    expect(defaultModelForGender('female')).toBe('female-straight')
    expect(defaultModelForGender('male')).toBe('male-straight')
  })

  it('exposes 10 selectable croquis and keeps legacy ids out of the picker list', () => {
    expect(BUILTIN_MODELS).toHaveLength(10)
    expect(BUILTIN_MODELS.filter((m) => m.gender === 'female')).toHaveLength(6)
    expect(BUILTIN_MODELS.filter((m) => m.gender === 'male')).toHaveLength(4)
    expect(BUILTIN_MODELS.some((m) => m.id === 'female' || m.id === 'male')).toBe(false)
    expect(BUILTIN_MODELS.every((m) => m.canvasSrc.startsWith('/models/library/'))).toBe(true)
  })

  it('resolves legacy female/male to the original croquis geometry', () => {
    expect(isLegacyModelId('female')).toBe(true)
    expect(isLegacyModelId('male')).toBe(true)
    expect(isLegacyModelId('female-straight')).toBe(false)
    expect(canvasSrcForModel('female')).toBe(LEGACY_MODEL_CANVAS.female)
    expect(canvasSrcForModel('male')).toBe(LEGACY_MODEL_CANVAS.male)
    expect(canvasSrcForModel('female')).toBe('/models/female_model.png')
    expect(canvasSrcForModel('male')).toBe('/models/male_model_display.png')
    expect(canvasSrcForModel('female')).not.toBe(canvasSrcForModel('female-straight'))
    expect(canvasSrcForModel('male')).not.toBe(canvasSrcForModel('male-straight'))
  })

  it('resolves new selectable models to library assets', () => {
    expect(canvasSrcForModel('female-straight')).toContain('female-straight')
    expect(canvasSrcForModel('male-straight')).toContain('male-straight')
    expect(canvasSrcForModel('female-hand-hip')).toContain('female-hand-hip')
    expect(canvasSrcForModel('blank')).toBeNull()
    expect(canvasSrcForModel('custom')).toBeNull()
  })

  it('preserves stored model ids without remapping legacy to new defaults', () => {
    expect(normalizeModelChoice('female')).toBe('female')
    expect(normalizeModelChoice('male')).toBe('male')
    expect(normalizeModelChoice('female-straight')).toBe('female-straight')
    expect(normalizeModelChoice('not-a-model')).toBe('female-straight')
    expect(isModelChoice('female')).toBe(true)
    expect(isModelChoice('female-contrapposto')).toBe(true)
    expect(isModelChoice('placeholder')).toBe(false)
  })

  it('labels legacy and new models distinctly', () => {
    expect(modelLabel('female')).toContain('Classic')
    expect(modelLabel('female-straight')).toContain('Standing')
    expect(modelLabel('male-straight')).toContain('Standing')
    expect(modelLabel('blank')).toBe('Blank paper')
  })
})
