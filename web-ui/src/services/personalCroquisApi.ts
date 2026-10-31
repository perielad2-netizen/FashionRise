import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

const BASE = '/personal-croquis'

export type AdultsAttestationRead = {
  id: string
  consent_version: string
  created_at: string
}

export type ConsentEventRead = {
  id: string
  purpose: string
  consent_version: string
  created_at: string
}

export type PersonalCroquisVersionSummary = {
  version: number
  status: string
  generated_asset_id: string | null
  accepted_at: string | null
}

export type PersonalCroquisRead = {
  id: string
  display_name: string | null
  source_asset_id: string
  archived_at: string | null
  erase_requested_at: string | null
  latest_accepted: PersonalCroquisVersionSummary | null
  created_at: string
  updated_at: string
}

export type PersonalCroquisVersionRead = {
  croquis_id: string
  version: number
  status: string
  generated_asset_id: string | null
  accepted_at: string | null
  geometry_profile: string | null
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

export async function attestAdults(
  body: AdultsAttestationRequest,
  signal?: AbortSignal,
): Promise<AdultsAttestationRead> {
  return apiRequest<AdultsAttestationRead>(`${BASE}/attestations/adults`, {
    method: 'POST',
    json: body,
    signal,
  })
}

export async function acknowledgeStorageConsent(
  body: ConsentAcknowledgeRequest,
  signal?: AbortSignal,
): Promise<ConsentEventRead> {
  return apiRequest<ConsentEventRead>(`${BASE}/consent/storage`, {
    method: 'POST',
    json: body,
    signal,
  })
}

export async function acknowledgeAiConsent(
  body: ConsentAcknowledgeRequest,
  signal?: AbortSignal,
): Promise<ConsentEventRead> {
  return apiRequest<ConsentEventRead>(`${BASE}/consent/ai`, {
    method: 'POST',
    json: body,
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

export async function uploadPersonalCroquisPhoto(
  file: File,
  storageConsentId: string,
  displayName?: string,
  signal?: AbortSignal,
): Promise<PersonalCroquisRead> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to upload a personal croquis photo.', 401, null)
  }
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('storage_consent_id', storageConsentId)
  if (displayName?.trim()) form.append('display_name', displayName.trim())

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
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
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
    const detail =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail: unknown }).detail === 'string'
        ? (parsed as { detail: string }).detail
        : 'Personal croquis upload failed'
    throw new ApiError(detail, response.status, parsed)
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
