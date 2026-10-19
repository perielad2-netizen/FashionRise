import { ApiError, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type ImageUploadResult = {
  url: string
  stored_key: string
}

export async function uploadReferenceImage(file: File, signal?: AbortSignal): Promise<ImageUploadResult> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to upload a reference image.', 401, null)
  }

  const form = new FormData()
  form.append('file', file, file.name)

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/uploads/image`, {
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
        : 'Upload failed'
    throw new ApiError(detail, response.status, parsed)
  }

  return parsed as ImageUploadResult
}
