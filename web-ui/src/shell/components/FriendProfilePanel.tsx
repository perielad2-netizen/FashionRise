import { useEffect, useState } from 'react'
import { ChevronLeft, UserPlus, UserMinus } from 'lucide-react'
import { useAuth } from '@/services/auth/AuthProvider'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { ApiError } from '@/services/api/client'
import type { FriendUser } from '@/services/friendsApi'
import { listUserGallery, type GalleryItem } from '@/services/galleryApi'
import {
  followCreator,
  getFollowStatus,
  getPublicProfile,
  unfollowCreator,
  type PublicProfile,
} from '@/services/profilesApi'
import styles from './RunwayScreen.module.css'

/** Minimal designer identity — friends circle or gallery creator. */
export type DesignerRef = {
  user_id: string
  username?: string
  display_name?: string
  avatar_url?: string | null
}

type Props = {
  friend: FriendUser | DesignerRef
  onBack: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; profile: PublicProfile | null; looks: GalleryItem[]; following: boolean }

/**
 * FashionRise designer profile — public bio, stats, published looks, follow.
 * Never loads private designs or unpublished looks.
 */
export function FriendProfilePanel({ friend, onBack }: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [followBusy, setFollowBusy] = useState(false)
  const label =
    friend.display_name ||
    friend.username ||
    (state.status === 'ready' ? state.profile?.display_name : null) ||
    'Designer'
  const isSelf = Boolean(viewerId && viewerId === friend.user_id)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    void Promise.all([
      getPublicProfile(friend.user_id, controller.signal).catch(() => null),
      listUserGallery(friend.user_id, controller.signal),
      viewerId && viewerId !== friend.user_id
        ? getFollowStatus(friend.user_id, controller.signal).catch(() => ({
            user_id: friend.user_id,
            following: false,
          }))
        : Promise.resolve({ user_id: friend.user_id, following: false }),
    ])
      .then(([profile, looks, follow]) => {
        if (controller.signal.aborted) return
        setState({
          status: 'ready',
          profile,
          looks,
          following: Boolean(follow?.following),
        })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          message:
            err instanceof ApiError ? err.message : 'Could not load this profile.',
        })
      })
    return () => controller.abort()
  }, [friend.user_id, viewerId])

  const onToggleFollow = async () => {
    if (!viewerId || isSelf || state.status !== 'ready' || followBusy) return
    const next = !state.following
    setFollowBusy(true)
    setState((prev) => (prev.status === 'ready' ? { ...prev, following: next } : prev))
    try {
      if (next) await followCreator(friend.user_id)
      else await unfollowCreator(friend.user_id)
    } catch {
      setState((prev) => (prev.status === 'ready' ? { ...prev, following: !next } : prev))
    } finally {
      setFollowBusy(false)
    }
  }

  return (
    <div className={styles.friendProfile} data-testid="friend-profile-panel">
      <header className={styles.friendProfileHead}>
        <button
          type="button"
          className={styles.friendBackBtn}
          onClick={onBack}
          data-testid="friend-profile-back"
        >
          <ChevronLeft size={18} aria-hidden />
          Back
        </button>
        <p className={styles.friendProfileEyebrow}>FashionRise designer</p>
      </header>

      <div className={styles.friendProfileIdentity}>
        {(() => {
          const avatarSrc =
            friend.avatar_url ||
            (state.status === 'ready' ? state.profile?.avatar_url : null) ||
            null
          return avatarSrc ? (
            <img
              src={avatarSrc}
              alt=""
              className={styles.friendAvatar}
              width={56}
              height={56}
            />
          ) : (
            <span className={styles.friendAvatarFallback} aria-hidden>
              {(label[0] || '?').toUpperCase()}
            </span>
          )
        })()}
        <div className={styles.friendText}>
          <strong data-testid="friend-profile-name">
            {state.status === 'ready' && state.profile?.display_name
              ? state.profile.display_name
              : label}
          </strong>
          {friend.username ? (
            <span data-testid="friend-profile-username">@{friend.username}</span>
          ) : null}
        </div>
      </div>

      {!isSelf && viewerId ? (
        <div className={styles.actions} style={{ marginTop: 8 }}>
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={followBusy || state.status !== 'ready'}
            data-testid="designer-follow-btn"
            onClick={() => void onToggleFollow()}
          >
            {state.status === 'ready' && state.following ? (
              <>
                <UserMinus size={14} aria-hidden />
                Following
              </>
            ) : (
              <>
                <UserPlus size={14} aria-hidden />
                Follow
              </>
            )}
          </button>
        </div>
      ) : null}

      {state.status === 'loading' ? (
        <p className={styles.status} role="status">
          Loading public profile…
        </p>
      ) : null}

      {state.status === 'error' ? (
        <p className={styles.status} role="alert">
          {state.message}
        </p>
      ) : null}

      {state.status === 'ready' ? (
        <>
          {state.profile?.bio ? (
            <p className={styles.friendBio} data-testid="friend-profile-bio">
              {state.profile.bio}
            </p>
          ) : (
            <p className={styles.friendBioMuted}>No public bio yet.</p>
          )}

          <ul className={styles.friendPublicStats} aria-label="Public stats">
            <li>
              <strong data-testid="friend-published-count">{state.looks.length}</strong>
              <span>Published</span>
            </li>
            {state.profile ? (
              <>
                <li>
                  <strong data-testid="designer-followers">{state.profile.followers_count}</strong>
                  <span>Followers</span>
                </li>
                <li>
                  <strong data-testid="designer-likes">{state.profile.likes_received_count}</strong>
                  <span>Likes</span>
                </li>
                <li>
                  <strong data-testid="designer-reputation">
                    {Math.round(state.profile.reputation_score)}
                  </strong>
                  <span>
                    Reputation
                    {state.profile.reputation_tier ? ` · ${state.profile.reputation_tier}` : ''}
                  </span>
                </li>
              </>
            ) : null}
          </ul>

          <section className={styles.friendLooksSection} aria-label="Published FashionRise looks">
            <h2 className={styles.friendSectionTitle}>Published on FashionRise</h2>
            {state.looks.length === 0 ? (
              <p className={styles.friendBioMuted} data-testid="friend-looks-empty">
                No published FashionRise looks yet.
              </p>
            ) : (
              <ul className={styles.friendLooksGrid}>
                {state.looks.map((item) => (
                  <li key={item.id}>
                    <FriendLookTile item={item} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}

function FriendLookTile({ item }: { item: GalleryItem }) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  return (
    <figure className={styles.friendLookTile} data-testid={`friend-look-${item.id}`}>
      {src ? (
        <img
          src={src}
          alt={item.title || 'Published FashionRise look'}
          className={styles.friendLookImage}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className={styles.friendLookPlaceholder} aria-hidden />
      )}
      <figcaption className={styles.friendLookCaption}>{item.title || 'Untitled look'}</figcaption>
    </figure>
  )
}
