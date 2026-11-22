import { apiRequest } from '@/services/api/client'

export type DesignShareResult = {
  collaboration_id: string
  message: string
  received_design: {
    id: string
    title: string
    user_id: string
    metadata?: Record<string, unknown> | null
  }
  transfer: {
    id: string
    from_username: string | null
    to_username: string | null
    fabrics_granted: number
    croquis_granted: number
    note: string | null
  }
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
