import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

const BASE = '/personal-croquis'

/** Mirrors Stage A `AdultsAttestationRead` / `ConsentEventRead`. */
export type AdultsAttestationRead = {
  id: string
  purpose: string
  consent_version: string
  adults_attested: boolean
  created_at: string
}

export type ConsentEventRead = {
  id: string
  purpose: string
  consent_version: string
  adults_attested: boolean
  created_at: string
}

/** Mirrors Stage A `PersonalCroquisVersionSummary`. */
export type PersonalCroquisVersionSummary = {
  version: number
  status: string
  generated_asset_id: string | null
  geometry_profile: string | null
  accepted_at: string | null
}

/**
 * Mirrors Stage A `PersonalCroquisRead` exactly.
 * Field names: `latest_accepted_version`, `archived`, `erased` (not archived_at / latest_accepted).
 */
/** Owner-declared presentation for Try On Person pants-vs-skirt disambiguation. */
export type CroquisSex = 'male' | 'female'

export type PersonalCroquisRead = {
  id: string
  display_name: string
  /** null on legacy models until the owner picks male/female. */
  sex?: CroquisSex | null
  status: string
  source_asset_id: string | null
  storage_consent_id: string | null
  adults_attestation_at: string | null
  archived: boolean
  erased: boolean
  created_at: string
  updated_at: string
  latest_accepted_version: PersonalCroquisVersionSummary | null
  /** Public FashionRise gallery item when published; private library otherwise. */
  fashionrise_item_id?: string | null
}

/** Mirrors Stage A `PersonalCroquisVersionRead`. */
export type PersonalCroquisVersionRead = {
  id: string
  croquis_id: string
  version: number
  status: string
  generated_asset_id: string | null
  geometry_profile: string | null
  prompt_version: string | null
  created_at: string
  accepted_at: string | null
  /** Present when status is failed / reconciliation_required (owner-safe). */
  failure_code?: string | null
  failure_message?: string | null
}

export type AdultsAttestationRequest = {
  adults_attested: true
  notice_version: string
  notice_text_hash: string
}

export type ConsentAcknowledgeRequest = {
  acknowledged: true
  adults_attested: true
  notice_version: string
  notice_text_hash: string
}

/** AI-provider consent must bind to the exact croquis source being generated. */
export type AiConsentAcknowledgeRequest = ConsentAcknowledgeRequest & {
  croquis_id: string
}

export async function attestAdults(
  body: AdultsAttestationRequest,
  signal?: AbortSignal,
): Promise<AdultsAttestationRead> {
  return apiRequest<AdultsAttestationRead>(`${BASE}/attestations/adults`, {
    method: 'POST',
    body,
    signal,
  })
}

export async function acknowledgeStorageConsent(
  body: ConsentAcknowledgeRequest,
  signal?: AbortSignal,
): Promise<ConsentEventRead> {
  return apiRequest<ConsentEventRead>(`${BASE}/consent/storage`, {
    method: 'POST',
    body,
    signal,
  })
}

export async function acknowledgeAiConsent(
  body: AiConsentAcknowledgeRequest,
  signal?: AbortSignal,
): Promise<ConsentEventRead> {
  return apiRequest<ConsentEventRead>(`${BASE}/consent/ai`, {
    method: 'POST',
    body,
    signal,
  })
}

/** Complete Create Model short+seven-point upload agreement (auditable). */
export async function acknowledgeCreateModelUploadConsent(
  body: ConsentAcknowledgeRequest,
  signal?: AbortSignal,
): Promise<ConsentEventRead> {
  return apiRequest<ConsentEventRead>(`${BASE}/consent/upload`, {
    method: 'POST',
    body,
    signal,
  })
}

export async function listPersonalCroquis(signal?: AbortSignal): Promise<PersonalCroquisRead[]> {
  return apiRequest<PersonalCroquisRead[]>(BASE, { signal })
}

export async function getPersonalCroquis(
  croquisId: string,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  return apiRequest<PersonalCroquisRead>(`${BASE}/${croquisId}`, { signal })
}

export async function getPersonalCroquisVersion(
  croquisId: string,
  version: number,
  signal?: AbortSignal,
): Promise<PersonalCroquisVersionRead> {
  return apiRequest<PersonalCroquisVersionRead>(`${BASE}/${croquisId}/versions/${version}`, {
    signal,
  })
}

export type GenerateVersionRequest = {
  ai_consent_id: string
  idempotency_key: string
}

/** Stage C enqueue — returns generating version; poll until awaiting_review / failed. */
export async function generatePersonalCroquisVersion(
  croquisId: string,
  body: GenerateVersionRequest,
  signal?: AbortSignal,
): Promise<PersonalCroquisVersionRead> {
  return apiRequest<PersonalCroquisVersionRead>(`${BASE}/${croquisId}/versions/generate`, {
    method: 'POST',
    body,
    signal,
  })
}

export async function acceptPersonalCroquisVersion(
  croquisId: string,
  version: number,
  signal?: AbortSignal,
): Promise<PersonalCroquisVersionRead> {
  return apiRequest<PersonalCroquisVersionRead>(
    `${BASE}/${croquisId}/versions/${version}/accept`,
    { method: 'POST', signal },
  )
}

export async function rejectPersonalCroquisVersion(
  croquisId: string,
  version: number,
  signal?: AbortSignal,
): Promise<PersonalCroquisVersionRead> {
  return apiRequest<PersonalCroquisVersionRead>(
    `${BASE}/${croquisId}/versions/${version}/reject`,
    { method: 'POST', signal },
  )
}

export async function updatePersonalCroquisSex(
  croquisId: string,
  sex: CroquisSex,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  return apiRequest<PersonalCroquisRead>(`${BASE}/${croquisId}/sex`, {
    method: 'PATCH',
    body: { sex },
    signal,
  })
}

/** Map FastAPI / proxy upload failures to owner-safe messages (no tokens/bytes). */
export function formatPersonalCroquisUploadError(
  status: number,
  parsed: unknown,
  fallback = 'Personal croquis upload failed',
): string {
  const detail = (parsed as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null
        const row = item as { loc?: unknown; msg?: unknown }
        const msg = typeof row.msg === 'string' ? row.msg.trim() : ''
        const loc = Array.isArray(row.loc)
          ? row.loc
              .filter((p): p is string | number => typeof p === 'string' || typeof p === 'number')
              .map(String)
          : []
        if (loc.includes('sex')) return 'Select male or female for this model.'
        return msg || null
      })
      .filter((m): m is string => Boolean(m))
    if (msgs.length) return msgs[0]
  }
  if (status === 401 || status === 403) {
    return 'Sign in expired. Sign in again, then retry Create Model.'
  }
  if (status === 413) {
    return 'That photo is too large to upload. Try a smaller photo, or wait while FashionRise compresses it and try again.'
  }
  if (status === 415 || status === 400) {
    return 'That photo could not be used. Choose a JPEG, PNG, or WebP fashion pose photo.'
  }
  if (status === 422) {
    return 'Create Model could not accept that upload. Check the photo and agreement, then try again.'
  }
  if (status === 0) {
    return 'Unable to reach FashionRise. Check your connection and try again.'
  }
  if (status >= 500) {
    return 'Server upload failed. Please try again in a moment.'
  }
  return fallback
}

export async function uploadPersonalCroquisPhoto(
  file: File,
  storageConsentId: string,
  options?: { displayName?: string; sex?: CroquisSex; signal?: AbortSignal },
): Promise<PersonalCroquisRead> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to upload a personal croquis photo.', 401, null)
  }
  const sex = options?.sex
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('storage_consent_id', storageConsentId)
  // Web Create Model sends sex; legacy native builds may omit it (BE accepts null).
  if (sex === 'male' || sex === 'female') form.append('sex', sex)
  if (options?.displayName?.trim()) form.append('display_name', options.displayName.trim())
  const signal = options?.signal

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${BASE}/photos`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokens.accessToken}`,
      },
      body: form,
      signal,
    })
  } catch {
    throw new ApiError(formatPersonalCroquisUploadError(0, null), 0, null)
  }

  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }
  if (!response.ok) {
    // Never log Authorization or image bytes — status + sanitized category only.
    if (typeof console !== 'undefined' && typeof console.warn === 'function') {
      console.warn('[create-model-upload]', {
        status: response.status,
        category: formatPersonalCroquisUploadError(response.status, parsed, 'upload_failed'),
      })
    }
    throw new ApiError(
      formatPersonalCroquisUploadError(response.status, parsed),
      response.status,
      parsed,
    )
  }
  return parsed as PersonalCroquisRead
}

export async function archivePersonalCroquis(
  croquisId: string,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  return apiRequest<PersonalCroquisRead>(`${BASE}/${croquisId}/archive`, {
    method: 'POST',
    signal,
  })
}

export async function erasePersonalCroquis(
  croquisId: string,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  return apiRequest<PersonalCroquisRead>(`${BASE}/${croquisId}`, {
    method: 'DELETE',
    signal,
  })
}

export type CroquisPublishPayload = {
  public_share_attested: true
  notice_version: string
  notice_text_hash: string
}

export type GalleryPublishResult = {
  id: string
  title: string
  image_url: string | null
}

export async function publishPersonalCroquisToFashionRise(
  croquisId: string,
  payload: CroquisPublishPayload,
  signal?: AbortSignal,
): Promise<GalleryPublishResult> {
  return apiRequest<GalleryPublishResult>(`${BASE}/${croquisId}/publish`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export async function unpublishPersonalCroquisFromFashionRise(
  croquisId: string,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  return apiRequest<PersonalCroquisRead>(`${BASE}/${croquisId}/publish`, {
    method: 'DELETE',
    signal,
  })
}

/** Owner-only private croquis bytes (never /static/uploads). */
export async function fetchCroquisAssetBlob(
  assetId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to load a personal croquis.', 401, null)
  }
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${BASE}/assets/${assetId}/image`, {
      method: 'GET',
      headers: {
        Accept: 'image/*,application/octet-stream',
        Authorization: `Bearer ${tokens.accessToken}`,
      },
      cache: 'no-store',
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }
  if (!response.ok) {
    throw new ApiError('Personal croquis image unavailable.', response.status, null)
  }
  return response.blob()
}

/** Accepted pin version from a Stage A croquis read (null when none / erased). */
export function acceptedVersionNumber(row: PersonalCroquisRead): number | null {
  if (row.erased) return null
  const ver = row.latest_accepted_version?.version
  return typeof ver === 'number' && ver > 0 ? ver : null
}
