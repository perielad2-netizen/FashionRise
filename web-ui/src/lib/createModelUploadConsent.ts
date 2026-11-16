/**
 * Create Model — private image upload consent (UI).
 *
 * Short checkbox + expandable full terms. Distinct from public-publish consent.
 * Backend still records separate adults / storage / AI events with versioned
 * notice hashes; those approved notices remain visible under the full terms.
 */

export const CREATE_MODEL_UPLOAD_CHECKBOX_LABEL =
  'I confirm I have the rights and permissions to use this photo and agree to private storage and AI processing.'

export const CREATE_MODEL_UPLOAD_FULL_TERMS_INTRO = 'By uploading this image, I confirm that:'

/** Exact expanded legal points for Create Model upload (private AI processing). */
export const CREATE_MODEL_UPLOAD_FULL_TERMS_POINTS: readonly string[] = [
  'I own the image or have the necessary rights, licenses or authorization to upload it and allow FashionRise and its authorized AI service providers to process and modify it.',
  'If an identifiable real person appears in the image, including a celebrity or public figure, I have all permissions or other lawful authorization required for the intended AI modifications and use of their likeness.',
  'I will not upload images that unlawfully infringe copyright, privacy, publicity, trademark or other rights, or that impersonate, deceive, exploit or harass other people.',
  'I will not upload nonconsensual intimate images, sexualized or humiliating manipulations of identifiable people, or sexualized depictions of minors.',
  'I understand that FashionRise may privately store and process my image, including through authorized third-party AI services, to generate my personal model, as described in the Privacy Policy.',
  'I understand that uploading an image does not automatically make it public. Publishing generated content requires a separate agreement.',
  'I accept responsibility for having the rights and permissions required for my submission. FashionRise may reject or remove content that violates its policies or applicable law.',
]
