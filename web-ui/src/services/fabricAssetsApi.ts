import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type FabricAsset = {
  id: string
  name: string
  content_type: string
  width: number
  height: number
  byte_size: number
  created_at: string
  deleted: boolean
}

export async function listMyFabrics(signal?: AbortSignal): Promise<FabricAsset[]> {
  return apiRequest<FabricAsset[]>('/fabrics', { signal })
}

export async function getFabricMeta(assetId: string, signal?: AbortSignal): Promise<FabricAsset> {
  return apiRequest<FabricAsset>(`/fabrics/${assetId}`, { signal })
}

export async function deleteFabric(assetId: string, signal?: AbortSignal): Promise<FabricAsset> {
  return apiRequest<FabricAsset>(`/fabrics/${assetId}`, { method: 'DELETE', signal })
}

export async function uploadFabric(
  file: File,
  name?: string,
  signal?: AbortSignal,
): Promise<FabricAsset> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to upload a fabric.', 401, null)
  }

  const form = new FormData()
  form.append('file', file, file.name)
  if (name && name.trim()) form.append('name', name.trim())

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/fabrics`, {
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
        : 'Fabric upload failed'
    throw new ApiError(detail, response.status, parsed)
  }

  return parsed as FabricAsset
}

/** Authenticated fabric bytes for canvas/export (never public static URLs). */
export async function fetchFabricImageBlob(assetId: string, signal?: AbortSignal): Promise<Blob> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to load this fabric.', 401, null)
  }

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/fabrics/${assetId}/image`, {
      method: 'GET',
      headers: {
        Accept: 'image/*',
        Authorization: `Bearer ${tokens.accessToken}`,
      },
      signal,
      cache: 'no-store',
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise to load this fabric.', 0, null)
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new ApiError('This fabric is missing or is not available for your account.', 404, null)
    }
    throw new ApiError('Could not load fabric image.', response.status, null)
  }

  const blob = await response.blob()
  if (!blob.size || (blob.type && !blob.type.startsWith('image/'))) {
    throw new ApiError('Fabric response was not an image.', response.status, null)
  }
  return blob
}
