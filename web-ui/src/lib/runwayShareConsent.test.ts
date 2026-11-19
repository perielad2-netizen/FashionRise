import { describe, expect, it } from 'vitest'
import {
  RUNWAY_SHARE_CHECKBOX_LABEL,
  RUNWAY_SHARE_NOTICE_TEXT,
  RUNWAY_SHARE_NOTICE_VERSION,
} from './runwayShareConsent'
import { CROQUIS_PUBLIC_SHARE_NOTICE_TEXT } from './croquisPublicShareConsent'
import { formatPublicPublishNoticeText } from './publicPublishConsent'

describe('runwayShareConsent', () => {
  it('keeps a stable versioned public-publish notice for Runway', () => {
    expect(RUNWAY_SHARE_NOTICE_VERSION).toBe('runway-share-2026-11-19')
    expect(RUNWAY_SHARE_NOTICE_TEXT).toBe(formatPublicPublishNoticeText())
    expect(RUNWAY_SHARE_NOTICE_TEXT).toBe(CROQUIS_PUBLIC_SHARE_NOTICE_TEXT)
    expect(RUNWAY_SHARE_CHECKBOX_LABEL).toMatch(/Publish & Earn/i)
    expect(RUNWAY_SHARE_CHECKBOX_LABEL).toMatch(/necessary rights/i)
    expect(RUNWAY_SHARE_NOTICE_TEXT.toLowerCase()).toContain('fashionrise')
    expect(RUNWAY_SHARE_NOTICE_TEXT.toLowerCase()).toContain('celebrities')
    expect(RUNWAY_SHARE_NOTICE_TEXT.toLowerCase()).not.toContain('unrelated advertising')
  })
})
