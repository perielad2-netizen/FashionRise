/**
 * Must stay in sync with backend `runway_share_consent_version` / notice text.
 * Public-publish wording is shared via publicPublishConsent (Runway remains a
 * separate product surface — only the legal agreement is standardized).
 */
import {
  formatPublicPublishNoticeText,
  PUBLIC_PUBLISH_CHECKBOX_LABEL,
} from './publicPublishConsent'

export const RUNWAY_SHARE_NOTICE_VERSION = 'runway-share-2026-11-17'

export const RUNWAY_SHARE_NOTICE_TEXT = formatPublicPublishNoticeText()

export const RUNWAY_SHARE_CHECKBOX_LABEL = PUBLIC_PUBLISH_CHECKBOX_LABEL
