import { useEffect, useRef, useState } from 'react'
import { Camera, ChevronLeft, UserMinus, UserPlus } from 'lucide-react'
import { useAuth } from '@/services/auth/AuthProvider'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { ApiError } from '@/services/api/client'
import type { FriendUser } from '@/services/friendsApi'
import { listUserGallery, type GalleryItem } from '@/services/galleryApi'
import {
  followCreator,
  getFollowStatus,
  getPublicProfile,
  updateMyProfile,
  unfollowCreator,
  type PublicProfile,
} from '@/services/profilesApi'
import { uploadReferenceImage } from '@/services/uploadsApi'
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
  /** When true and viewing self, open the existing Edit Profile form once ready. */
  startInEditMode?: boolean
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; profile: PublicProfile | null; looks: GalleryItem[]; following: boolean }

/**
 * FashionRise designer profile — public bio, stats, published looks, follow.
 * Never loads private designs or unpublished looks.
 */
export function FriendProfilePanel({ friend, onBack, startInEditMode = false }: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [followBusy, setFollowBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editBio, setEditBio] = useState('')
  const [editBusy, setEditBusy] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const openedEditRef = useRef(false)
  const label =
    friend.display_name ||
    friend.username ||
    (state.status === 'ready' ? state.profile?.display_name : null) ||
    'Designer'
  const isSelf = Boolean(viewerId && viewerId === friend.user_id)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    setEditing(false)
    openedEditRef.current = false
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

  const beginEdit = () => {
    if (state.status !== 'ready' || !isSelf) return
    setEditName(state.profile?.display_name || friend.display_name || '')
    setEditBio(state.profile?.bio || '')
    setEditError(null)
    setEditing(true)
  }

  useEffect(() => {
    if (!startInEditMode || !isSelf || openedEditRef.current) return
    if (state.status !== 'ready') return
    openedEditRef.current = true
    beginEdit()
  }, [startInEditMode, isSelf, state])

  const saveProfile = async () => {
    if (editBusy || state.status !== 'ready') return
    setEditBusy(true)
    setEditError(null)
    try {
      const next = await updateMyProfile({
        display_name: editName.trim().slice(0, 120) || undefined,
        bio: editBio.trim() ? editBio.trim().slice(0, 2000) : '',
      })
      setState((prev) =>
        prev.status === 'ready' ? { ...prev, profile: { ...prev.profile!, ...next } } : prev,
      )
      setEditing(false)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Could not save profile')
    } finally {
      setEditBusy(false)
    }
  }

  const onAvatarSelected = async (file: File | null) => {
    if (!file || editBusy || state.status !== 'ready') return
    setEditBusy(true)
    setEditError(null)
    try {
      const uploaded = await uploadReferenceImage(file)
      const next = await updateMyProfile({ avatar_url: uploaded.url })
      setState((prev) =>
        prev.status === 'ready' ? { ...prev, profile: { ...prev.profile!, ...next } } : prev,
      )
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Could not update photo')
    } finally {
      setEditBusy(false)
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
            (state.status === 'ready' ? state.profile?.avatar_url : null) ||
            friend.avatar_url ||
            null
          const avatarNode = avatarSrc ? (
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
          if (isSelf && editing) {
            return (
              <button
                type="button"
                className={styles.friendAvatarEdit}
                data-testid="designer-avatar-preview"
                aria-label="Change profile photo"
                disabled={editBusy}
                onClick={() => avatarInputRef.current?.click()}
              >
                {avatarNode}
                <span className={styles.friendAvatarEditBadge} aria-hidden>
                  <Camera size={13} />
                </span>
              </button>
            )
          }
          return avatarNode
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
      {isSelf && editing ? (
        <p className={styles.friendAvatarHint}>
          Your photo updates here — and on your looks across FashionRise.
        </p>
      ) : null}

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

      {isSelf && state.status === 'ready' ? (
        <div className={styles.actions} style={{ marginTop: 8 }}>
          {!editing ? (
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid="designer-edit-profile"
              onClick={beginEdit}
            >
              Edit profile
            </button>
          ) : null}
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            data-testid="designer-avatar-input"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null
              e.target.value = ''
              void onAvatarSelected(file)
            }}
          />
        </div>
      ) : null}

      {isSelf && editing ? (
        <form
          className={styles.friendEditForm}
          data-testid="designer-profile-editor"
          onSubmit={(e) => {
            e.preventDefault()
            void saveProfile()
          }}
        >
          <label className={styles.friendEditLabel}>
            Display name
            <input
              className={styles.friendEditInput}
              value={editName}
              maxLength={120}
              disabled={editBusy}
              data-testid="designer-edit-name"
              onChange={(e) => setEditName(e.target.value)}
            />
          </label>
          <label className={styles.friendEditLabel}>
            Bio
            <textarea
              className={styles.friendEditTextarea}
              value={editBio}
              maxLength={2000}
              rows={3}
              disabled={editBusy}
              data-testid="designer-edit-bio"
              onChange={(e) => setEditBio(e.target.value)}
            />
          </label>
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={editBusy}
              onClick={() => avatarInputRef.current?.click()}
              data-testid="designer-edit-avatar"
            >
              <Camera size={14} aria-hidden />
              Change photo
            </button>
            <button type="submit" className={styles.primaryBtn} disabled={editBusy}>
              {editBusy ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={editBusy}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
          {editError ? (
            <p className={styles.status} role="alert">
              {editError}
            </p>
          ) : null}
        </form>
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
