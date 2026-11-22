import { apiRequest } from '@/services/api/client'

export type DesignShareTransfer = {
  id: string
  collaboration_id: string
  from_user_id: string
  to_user_id: string
  source_design_id: string | null
  received_design_id: string | null
  note: string | null
  status: 'pending' | 'accepted' | 'rejected' | string
  source_title: string | null
  responded_at: string | null
  created_at: string
  from_username: string | null
  to_username: string | null
  fabrics_granted: number
  croquis_granted: number
}

export type DesignShareResult = {
  collaboration_id: string
  message: string
  received_design: {
    id: string
    title: string
    user_id: string
    metadata?: Record<string, unknown> | null
  } | null
  transfer: DesignShareTransfer
}

export async function shareDesignWithFriend(
  designId: string,
  friendUserId: string,
  note?: string,
  signal?: AbortSignal,
): Promise<DesignShareResult> {
  return apiRequest<DesignShareResult>(`/designs/${designId}/share`, {
    method: 'POST',
    body: {
      friend_user_id: friendUserId,
      ...(note && note.trim() ? { note: note.trim() } : {}),
    },
    signal,
  })
}

export async function listIncomingDesignShares(
  signal?: AbortSignal,
): Promise<DesignShareTransfer[]> {
  return apiRequest<DesignShareTransfer[]>('/designs/shares/incoming', { signal })
}

export async function acceptDesignShare(
  transferId: string,
  signal?: AbortSignal,
): Promise<DesignShareResult> {
  return apiRequest<DesignShareResult>(`/designs/shares/${transferId}/accept`, {
    method: 'POST',
    signal,
  })
}

export async function rejectDesignShare(
  transferId: string,
  signal?: AbortSignal,
): Promise<DesignShareTransfer> {
  return apiRequest<DesignShareTransfer>(`/designs/shares/${transferId}/reject`, {
    method: 'POST',
    signal,
  })
}
