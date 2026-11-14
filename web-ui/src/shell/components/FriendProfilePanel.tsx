import { useEffect, useState } from 'react'
import { ChevronLeft } from 'lucide-react'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { ApiError } from '@/services/api/client'
import type { FriendUser } from '@/services/friendsApi'
import { listUserGallery, type GalleryItem } from '@/services/galleryApi'
import { getPublicProfile, type PublicProfile } from '@/services/profilesApi'
import styles from './RunwayScreen.module.css'

type Props = {
  friend: FriendUser
  onBack: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; profile: PublicProfile | null; looks: GalleryItem[] }

/**
 * V2-0010 — read-only friend profile + published Runway looks.
 * Never loads private designs or unpublished looks.
 */
export function FriendProfilePanel({ friend, onBack }: Props) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const label = friend.display_name || friend.username

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    void Promise.all([
      getPublicProfile(friend.user_id, controller.signal).catch(() => null),
      listUserGallery(friend.user_id, controller.signal),
    ])
      .then(([profile, looks]) => {
        if (controller.signal.aborted) return
        setState({ status: 'ready', profile, looks })
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
  }, [friend.user_id])

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
        <p className={styles.friendProfileEyebrow}>Friend profile</p>
      </header>

      <div className={styles.friendProfileIdentity}>
        {friend.avatar_url ? (
          <img
            src={friend.avatar_url}
            alt=""
            className={styles.friendAvatar}
            width={56}
            height={56}
          />
        ) : (
          <span className={styles.friendAvatarFallback} aria-hidden>
            {(label[0] || '?').toUpperCase()}
          </span>
        )}
        <div className={styles.friendText}>
          <strong data-testid="friend-profile-name">{label}</strong>
          <span data-testid="friend-profile-username">@{friend.username}</span>
        </div>
      </div>

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
              <span>Published looks</span>
            </li>
            {state.profile ? (
              <li>
                <strong>{state.profile.followers_count}</strong>
                <span>Followers</span>
              </li>
            ) : null}
          </ul>

          <section className={styles.friendLooksSection} aria-label="Published Runway looks">
            <h2 className={styles.friendSectionTitle}>Published on Runway</h2>
            {state.looks.length === 0 ? (
              <p className={styles.friendBioMuted} data-testid="friend-looks-empty">
                No published Runway looks yet.
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
          alt={item.title || 'Published Runway look'}
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
