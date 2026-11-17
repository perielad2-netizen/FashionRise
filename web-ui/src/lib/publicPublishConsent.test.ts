import { describe, expect, it } from 'vitest'
import {
  formatPublicPublishNoticeText,
  PUBLIC_PUBLISH_CHECKBOX_LABEL,
  PUBLIC_PUBLISH_FULL_TERMS_POINTS,
} from './publicPublishConsent'
import {
  CREATE_MODEL_UPLOAD_CHECKBOX_LABEL,
  CREATE_MODEL_UPLOAD_FULL_TERMS_POINTS,
  CREATE_MODEL_UPLOAD_NOTICE_VERSION,
  formatCreateModelUploadNoticeText,
} from './createModelUploadConsent'

describe('public vs upload consent separation', () => {
  it('keeps upload and publish short labels distinct', () => {
    expect(CREATE_MODEL_UPLOAD_CHECKBOX_LABEL).toMatch(/private storage and AI processing/i)
    expect(PUBLIC_PUBLISH_CHECKBOX_LABEL).toMatch(/display it publicly/i)
    expect(CREATE_MODEL_UPLOAD_CHECKBOX_LABEL).not.toEqual(PUBLIC_PUBLISH_CHECKBOX_LABEL)
  })

  it('upload full terms state upload is not public publish', () => {
    const joined = CREATE_MODEL_UPLOAD_FULL_TERMS_POINTS.join(' ')
    expect(joined).toMatch(/does not automatically make it public/i)
    expect(joined).toMatch(/separate agreement/i)
  })

  it('hashes a stable create-model upload notice including short checkbox copy', () => {
    expect(CREATE_MODEL_UPLOAD_NOTICE_VERSION).toBe('create-model-upload-2026-11-17')
    const text = formatCreateModelUploadNoticeText()
    expect(text.startsWith(CREATE_MODEL_UPLOAD_CHECKBOX_LABEL)).toBe(true)
    expect(text).toContain('By uploading this image, I confirm that:')
    expect(text).toContain('1. I own the image')
    expect(text).toContain('7. I accept responsibility')
  })

  it('publish notice includes platform operating license without advertising expansion', () => {
    expect(PUBLIC_PUBLISH_FULL_TERMS_POINTS).toHaveLength(8)
    const text = formatPublicPublishNoticeText()
    expect(text).toContain('By publishing this content, I confirm that:')
    expect(text).toMatch(/non-exclusive, worldwide, royalty-free license/i)
    expect(text).toMatch(/operate FashionRise/i)
    expect(text.toLowerCase()).not.toContain('advertising')
  })
})
