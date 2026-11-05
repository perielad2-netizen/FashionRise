import { describe, expect, it } from 'vitest'
import {
  clearFabricPromptCache,
  getFabricPromptShort,
  rememberFabricAssets,
  rememberFabricPromptShort,
} from '@/lib/fabricPromptCache'

describe('fabricPromptCache', () => {
  it('stores and clears short prompts for Magic', () => {
    clearFabricPromptCache()
    rememberFabricPromptShort('AAA', 'gold glitter metallic')
    expect(getFabricPromptShort('aaa')).toBe('gold glitter metallic')
    rememberFabricAssets([{ id: 'bbb', prompt_short: 'navy sequin fabric' }])
    expect(getFabricPromptShort('BBB')).toBe('navy sequin fabric')
    rememberFabricPromptShort('aaa', null)
    expect(getFabricPromptShort('aaa')).toBeNull()
    clearFabricPromptCache()
    expect(getFabricPromptShort('bbb')).toBeNull()
  })
})
