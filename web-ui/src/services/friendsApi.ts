import { apiRequest } from '@/services/api/client'

export type FriendUser = {
  user_id: string
  username: string
  display_name: string
  avatar_url: string | null
}

export type Friendship = {
  id: string
  status: 'pending' | 'accepted' | string
  requester_id: string
  addressee_id: string
  created_at: string
  accepted_at: string | null
  friend: FriendUser
}

export async function listFriends(signal?: AbortSignal): Promise<Friendship[]> {
  return apiRequest<Friendship[]>('/friends', { signal })
}

export async function listFriendRequests(signal?: AbortSignal): Promise<Friendship[]> {
  return apiRequest<Friendship[]>('/friends/requests', { signal })
}

export async function requestFriendByUsername(
  username: string,
  signal?: AbortSignal,
): Promise<Friendship> {
  return apiRequest<Friendship>('/friends/request', {
    method: 'POST',
    body: { username: username.trim() },
    signal,
  })
}

export async function acceptFriendRequest(
  friendshipId: string,
  signal?: AbortSignal,
): Promise<Friendship> {
  return apiRequest<Friendship>(`/friends/${friendshipId}/accept`, {
    method: 'POST',
    signal,
  })
}

export async function removeFriend(friendUserId: string, signal?: AbortSignal): Promise<void> {
  await apiRequest<void>(`/friends/${friendUserId}`, {
    method: 'DELETE',
    signal,
  })
}
