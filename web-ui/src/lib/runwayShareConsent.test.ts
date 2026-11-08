import { describe, expect, it } from 'vitest'
import {
  RUNWAY_SHARE_CHECKBOX_LABEL,
  RUNWAY_SHARE_NOTICE_TEXT,
  RUNWAY_SHARE_NOTICE_VERSION,
} from './runwayShareConsent'

describe('runwayShareConsent', () => {
  it('keeps a stable versioned notice for Runway publish', () => {
    expect(RUNWAY_SHARE_NOTICE_VERSION).toMatch(/^runway-share-/)
    expect(RUNWAY_SHARE_NOTICE_TEXT.toLowerCase()).toContain('fashionrise')
    expect(RUNWAY_SHARE_NOTICE_TEXT.toLowerCase()).toContain('runway')
    expect(RUNWAY_SHARE_CHECKBOX_LABEL.toLowerCase()).toContain('rights to share')
    expect(RUNWAY_SHARE_CHECKBOX_LABEL.toLowerCase()).toContain('permission to display')
  })
})
