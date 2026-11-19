/**
 * Must stay in sync with backend `croquis_public_share_consent_version` / notice text.
 * My Models → FashionRise public publish uses the same public-publish agreement
 * as other gallery publication paths (UI may be gated separately).
 */
import {
  formatPublicPublishNoticeText,
  PUBLIC_PUBLISH_CHECKBOX_LABEL,
} from './publicPublishConsent'

export const CROQUIS_PUBLIC_SHARE_NOTICE_VERSION = 'croquis-public-share-2026-11-19'

export const CROQUIS_PUBLIC_SHARE_NOTICE_TEXT = formatPublicPublishNoticeText()

export const CROQUIS_PUBLIC_SHARE_CHECKBOX_LABEL = PUBLIC_PUBLISH_CHECKBOX_LABEL
