import { describe, expect, it } from 'vitest'
import {
  BUILTIN_MODELS,
  DEFAULT_FEMALE_MODEL,
  DEFAULT_MALE_MODEL,
  DEFAULT_MODEL,
  canvasSrcForModel,
  defaultModelForGender,
  isModelChoice,
  modelLabel,
  normalizeModelChoice,
} from '@/assets/modelLibrary'

describe('modelLibrary', () => {
  it('defaults to female standing and male standing', () => {
    expect(DEFAULT_MODEL).toBe('female')
    expect(DEFAULT_FEMALE_MODEL).toBe('female')
    expect(DEFAULT_MALE_MODEL).toBe('male')
    expect(defaultModelForGender('female')).toBe('female')
    expect(defaultModelForGender('male')).toBe('male')
  })

  it('exposes only available built-in croquis (no placeholders)', () => {
    expect(BUILTIN_MODELS.length).toBeGreaterThanOrEqual(8)
    expect(BUILTIN_MODELS.every((m) => m.canvasSrc && m.cardSrc)).toBe(true)
    expect(BUILTIN_MODELS.filter((m) => m.gender === 'female').length).toBe(6)
    expect(BUILTIN_MODELS.filter((m) => m.gender === 'male').length).toBe(4)
  })

  it('resolves canvas URLs for built-ins and null for blank', () => {
    expect(canvasSrcForModel('female')).toContain('female-straight')
    expect(canvasSrcForModel('male')).toContain('male-straight')
    expect(canvasSrcForModel('female-hand-hip')).toContain('female-hand-hip')
    expect(canvasSrcForModel('blank')).toBeNull()
    expect(canvasSrcForModel('custom')).toBeNull()
  })

  it('normalizes legacy aliases and unknown values', () => {
    expect(normalizeModelChoice('female-straight')).toBe('female')
    expect(normalizeModelChoice('male-straight')).toBe('male')
    expect(normalizeModelChoice('not-a-model')).toBe('female')
    expect(isModelChoice('female-contrapposto')).toBe(true)
    expect(isModelChoice('placeholder')).toBe(false)
  })

  it('labels models for UI copy', () => {
    expect(modelLabel('female')).toContain('Standing')
    expect(modelLabel('male')).toContain('Standing')
    expect(modelLabel('blank')).toBe('Blank paper')
  })
})
