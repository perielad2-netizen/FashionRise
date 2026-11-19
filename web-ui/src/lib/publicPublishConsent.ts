/**
 * Public publishing consent — shared wording for Runway, FashionRise Social
 * gallery listing, and My Models public publish (when that UI is available).
 *
 * Versioned notice text must stay byte-identical with backend settings
 * (`runway_share_notice_text` / `croquis_public_share_notice_text` as applicable).
 * Upload/Create Model consent never authorizes public publishing.
 */

export const PUBLIC_PUBLISH_CHECKBOX_LABEL =
  'Publish & Earn ⭐\n\n' +
  'I agree to let others virtually try on my design using AI. I grant the app a non-exclusive license for this use and confirm I have the necessary rights.\n\n' +
  'I earn 2 Stars for each successfully completed AI try-on. My rights remain mine, and I can remove my design from future try-ons at any time.'

export const PUBLIC_PUBLISH_FULL_TERMS_INTRO = 'By publishing this content, I confirm that:'

export const PUBLIC_PUBLISH_FULL_TERMS_POINTS: readonly string[] = [
  'I own the content or have all necessary rights and permissions for its public use, including the original images, AI-generated or modified elements, artwork, logos, trademarks and other third-party materials.',
  'If identifiable people appear in the content, including celebrities or public figures, I have the necessary consent or other lawful authorization for their appearance, any relevant AI modifications and the intended public use.',
  'My content does not unlawfully infringe another person\'s copyright, privacy, publicity, personality, trademark or other legal rights.',
  'My content does not falsely imply that another person or brand endorses FashionRise, my design or any product.',
  'I will not publish deceptive impersonations, nonconsensual intimate imagery, exploitative or humiliating depictions, or sexualized depictions of minors.',
  'I grant FashionRise a non-exclusive, worldwide, royalty-free license to host, reproduce, display, distribute and technically adapt this published content as reasonably necessary to operate FashionRise, including public feeds, designer profiles, previews, rankings, sharing, competitions and virtual AI try-on of my design by other users.',
  'I understand that publication makes my content visible to other users, and FashionRise may restrict or remove it in response to violations, legal complaints or applicable law.',
  'I accept responsibility for my submissions and for having the rights and permissions required to publish them.',
  'I agree to let others virtually try on my design using AI and confirm I have the necessary rights for that use.',
  'I earn 2 Stars for each successfully completed AI try-on of my published design by other users. My rights remain mine, and I can remove my design from future try-ons at any time.',
]

/** Joined body hashed/sent as the approved notice (must match backend). */
export function formatPublicPublishNoticeText(): string {
  const points = PUBLIC_PUBLISH_FULL_TERMS_POINTS.map((p, i) => `${i + 1}. ${p}`).join('\n')
  return `${PUBLIC_PUBLISH_FULL_TERMS_INTRO}\n\n${points}`
}
