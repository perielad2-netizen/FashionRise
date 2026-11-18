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

export type FriendRelationship = 'none' | 'pending_out' | 'pending_in' | 'accepted' | string

export type FriendSearchHit = {
  user: FriendUser
  relationship: FriendRelationship
  friendship_id: string | null
}

export async function listFriends(signal?: AbortSignal): Promise<Friendship[]> {
  return apiRequest<Friendship[]>('/friends', { signal })
}

export async function listFriendRequests(signal?: AbortSignal): Promise<Friendship[]> {
  return apiRequest<Friendship[]>('/friends/requests', { signal })
}

export async function searchFriends(
  query: string,
  signal?: AbortSignal,
): Promise<FriendSearchHit[]> {
  const q = query.trim()
  const params = new URLSearchParams({ q })
  return apiRequest<FriendSearchHit[]>(`/friends/search?${params}`, { signal })
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

export async function requestFriendByUserId(
  userId: string,
  signal?: AbortSignal,
): Promise<Friendship> {
  return apiRequest<Friendship>('/friends/request', {
    method: 'POST',
    body: { user_id: userId },
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

export async function rejectFriendRequest(
  friendshipId: string,
  signal?: AbortSignal,
): Promise<void> {
  await apiRequest<void>(`/friends/${friendshipId}/reject`, {
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
