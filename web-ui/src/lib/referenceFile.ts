export const ALLOWED_REFERENCE_MIME = ['image/jpeg', 'image/png', 'image/webp'] as const

export type AllowedReferenceMime = (typeof ALLOWED_REFERENCE_MIME)[number]

export function isAllowedReferenceMime(mime: string): mime is AllowedReferenceMime {
  return (ALLOWED_REFERENCE_MIME as readonly string[]).includes(mime)
}

export type ReferenceFileValidation =
  | { ok: true }
  | { ok: false; message: string }

export function validateReferenceImageFile(file: File): ReferenceFileValidation {
  if (!isAllowedReferenceMime(file.type)) {
    return {
      ok: false,
      message: 'Please choose a JPEG, PNG, or WebP image.',
    }
  }
  return { ok: true }
}
