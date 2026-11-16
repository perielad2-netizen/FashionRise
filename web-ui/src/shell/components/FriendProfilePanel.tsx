import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Camera, UserMinus, UserPlus, X } from 'lucide-react'
import { useAuth } from '@/services/auth/AuthProvider'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { ApiError } from '@/services/api/client'
import type { FriendUser } from '@/services/friendsApi'
import { listUserGallery, type GalleryItem } from '@/services/galleryApi'
import {
  followCreator,
  getFollowStatus,
  getPublicProfile,
  profileAvatarSrc,
  updateMyProfile,
  unfollowCreator,
  uploadMyAvatar,
  type PublicProfile,
} from '@/services/profilesApi'
import { AvatarCropDialog } from './AvatarCropDialog'
import styles from './FriendProfilePanel.module.css'

/** Minimal designer identity — friends circle or gallery creator. */
export type DesignerRef = {
  user_id: string
  username?: string
  display_name?: string
  avatar_url?: string | null
}

type Props = {
  friend: FriendUser | DesignerRef
  /** When true and viewing self, open the Edit Designer Card sheet once ready. */
  startInEditMode?: boolean
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; profile: PublicProfile | null; looks: GalleryItem[]; following: boolean }

function heroToneClass(userId: string): string {
  let hash = 0
  for (let i = 0; i < userId.length; i += 1) hash = (hash * 31 + userId.charCodeAt(i)) >>> 0
  const tone = hash % 3
  if (tone === 1) return styles.heroToneB
  if (tone === 2) return styles.heroToneC
  return styles.heroToneA
}

function tierLabel(tier: string | null | undefined): string | null {
  const t = (tier || '').trim()
  if (!t) return null
  return t.replace(/_/g, ' ')
}

/**
 * FashionRise designer profile — premium brand cover, follow, published collection.
 * Never loads private designs or unpublished looks.
 */
export function FriendProfilePanel({ friend, startInEditMode = false }: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [followBusy, setFollowBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editBio, setEditBio] = useState('')
  const [editBusy, setEditBusy] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [cropFile, setCropFile] = useState<File | null>(null)
  const [localAvatarPreview, setLocalAvatarPreview] = useState<string | null>(null)
  const [previewLook, setPreviewLook] = useState<GalleryItem | null>(null)
  const [previewAvatar, setPreviewAvatar] = useState(false)
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const openedEditRef = useRef(false)
  const editTitleId = useId()
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
    setPreviewLook(null)
    setPreviewAvatar(false)
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

  const onAvatarPicked = (file: File | null) => {
    if (!file || editBusy || state.status !== 'ready') return
    setEditError(null)
    setCropFile(file)
  }

  const onAvatarCropConfirm = async (cropped: File) => {
    if (editBusy || state.status !== 'ready') return
    setEditBusy(true)
    setEditError(null)
    const preview = URL.createObjectURL(cropped)
    setLocalAvatarPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return preview
    })
    try {
      const next = await uploadMyAvatar(cropped)
      setState((prev) =>
        prev.status === 'ready' ? { ...prev, profile: { ...prev.profile!, ...next } } : prev,
      )
      setCropFile(null)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Could not update photo')
      setLocalAvatarPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
    } finally {
      setEditBusy(false)
    }
  }

  useEffect(() => {
    return () => {
      if (localAvatarPreview) URL.revokeObjectURL(localAvatarPreview)
    }
  }, [localAvatarPreview])

  useEffect(() => {
    if (!editing && !previewLook) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (cropFile) return
      if (previewLook) setPreviewLook(null)
      else if (editing && !editBusy) setEditing(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [editing, previewLook, cropFile, editBusy])

  const displayName =
    state.status === 'ready' && state.profile?.display_name
      ? state.profile.display_name
      : label
  const bio = state.status === 'ready' ? state.profile?.bio?.trim() || '' : ''
  const tagline = bio.length > 0 && bio.length <= 120 ? bio : null
  const longBio = bio.length > 120 ? bio : null
  const tier = state.status === 'ready' ? tierLabel(state.profile?.reputation_tier) : null
  const coverUrl =
    state.status === 'ready' && state.profile?.cover_url ? state.profile.cover_url : null
  const [avatarBroken, setAvatarBroken] = useState(false)
  const avatarSrc =
    localAvatarPreview ||
    profileAvatarSrc(
      friend.user_id,
      (state.status === 'ready' ? state.profile?.avatar_url : null) || friend.avatar_url || null,
      state.status === 'ready' ? state.profile?.updated_at : null,
    )
  const showAvatarPhoto = Boolean(avatarSrc) && !avatarBroken

  useEffect(() => {
    setAvatarBroken(false)
  }, [avatarSrc])

  const avatarFallback = (
    <span className={styles.avatarFallback} aria-hidden data-testid="designer-avatar-fallback">
      {(displayName[0] || '?').toUpperCase()}
    </span>
  )

  const avatarNode = showAvatarPhoto ? (
    <img
      src={avatarSrc!}
      alt=""
      className={styles.avatar}
      width={84}
      height={84}
      data-testid="designer-avatar-photo"
      onError={() => setAvatarBroken(true)}
    />
  ) : (
    avatarFallback
  )

  const heroAvatar = showAvatarPhoto ? (
    <button
      type="button"
      className={styles.avatarBtn}
      data-testid="designer-avatar-open"
      aria-label={`View ${displayName}'s profile photo`}
      onClick={() => setPreviewAvatar(true)}
    >
      {avatarNode}
    </button>
  ) : (
    avatarNode
  )

  const heroTone = useMemo(() => heroToneClass(friend.user_id), [friend.user_id])

  return (
    <div className={styles.panel} data-testid="friend-profile-panel">
      <section className={`${styles.hero} ${heroTone}`} aria-label="Designer card">
        {coverUrl ? (
          <div
            className={styles.heroCover}
            style={{ backgroundImage: `url("${coverUrl.replace(/["\\]/g, '')}")` }}
            aria-hidden
          />
        ) : null}
        <div className={styles.heroVeil} aria-hidden />
        <div className={styles.heroBody}>
          <div className={styles.heroTop}>
            {heroAvatar}
            <div className={styles.identity}>
              <h1 className={styles.displayName} data-testid="friend-profile-name">
                {displayName}
              </h1>
              {friend.username ? (
                <p className={styles.handle} data-testid="friend-profile-username">
                  @{friend.username}
                </p>
              ) : null}
              {tier ? (
                <span className={styles.tierBadge} data-testid="designer-tier-badge">
                  {tier}
                </span>
              ) : null}
            </div>
          </div>

          {tagline ? (
            <p className={styles.tagline} data-testid="friend-profile-bio">
              {tagline}
            </p>
          ) : null}

          <div className={styles.heroActions}>
            {!isSelf && viewerId ? (
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
            ) : null}
            {isSelf && state.status === 'ready' ? (
              <button
                type="button"
                className={styles.primaryBtn}
                data-testid="designer-edit-profile"
                onClick={beginEdit}
              >
                Edit Designer Card
              </button>
            ) : null}
          </div>

          {state.status === 'ready' ? (
            <ul className={styles.stats} aria-label="Public stats">
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
                    <span>Reputation</span>
                  </li>
                </>
              ) : null}
            </ul>
          ) : null}
        </div>
      </section>

      {state.status === 'loading' ? (
        <p className={styles.status} role="status">
          Loading designer profile…
        </p>
      ) : null}

      {state.status === 'error' ? (
        <p className={styles.status} role="alert">
          {state.message}
        </p>
      ) : null}

      {state.status === 'ready' && longBio ? (
        <p className={styles.bioBlock} data-testid="friend-profile-bio-long">
          {longBio}
        </p>
      ) : null}

      {state.status === 'ready' ? (
        <section className={styles.collection} aria-label="Published FashionRise looks">
          <div className={styles.collectionHead}>
            <h2 className={styles.collectionTitle}>Collection</h2>
            <span className={styles.collectionMeta}>{state.looks.length} looks</span>
          </div>
          {state.looks.length === 0 ? (
            <p className={styles.emptyLooks} data-testid="friend-looks-empty">
              No published FashionRise looks yet.
            </p>
          ) : (
            <ul className={styles.looksGrid}>
              {state.looks.map((item) => (
                <li key={item.id}>
                  <FriendLookTile item={item} onOpen={() => setPreviewLook(item)} />
                </li>
              ))}
            </ul>
          )}
        </section>
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
          onAvatarPicked(file)
        }}
      />

      {cropFile ? (
        <AvatarCropDialog
          file={cropFile}
          busy={editBusy}
          onCancel={() => {
            if (editBusy) return
            setCropFile(null)
          }}
          onConfirm={(cropped) => void onAvatarCropConfirm(cropped)}
        />
      ) : null}

      {isSelf && editing ? (
        <div
          className={styles.sheetBackdrop}
          role="presentation"
          data-testid="designer-profile-editor"
          onClick={() => {
            if (!editBusy) setEditing(false)
          }}
        >
          <div
            className={styles.sheet}
            role="dialog"
            aria-modal="true"
            aria-labelledby={editTitleId}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={editTitleId} className={styles.sheetTitle}>
              Edit Designer Card
            </h2>
            <p className={styles.sheetHint}>
              Your photo and bio appear on your FashionRise profile and published looks.
            </p>
            <div className={styles.editIdentity}>
              <button
                type="button"
                className={styles.avatarEdit}
                data-testid="designer-avatar-preview"
                aria-label="Change profile photo"
                disabled={editBusy}
                onClick={() => avatarInputRef.current?.click()}
              >
                {avatarNode}
                <span className={styles.avatarBadge} aria-hidden>
                  <Camera size={13} />
                </span>
              </button>
              <div>
                <strong>{displayName}</strong>
                {friend.username ? <div className={styles.handle}>@{friend.username}</div> : null}
              </div>
            </div>
            <form
              className={styles.editForm}
              onSubmit={(e) => {
                e.preventDefault()
                void saveProfile()
              }}
            >
              <label className={styles.editLabel}>
                Display name
                <input
                  className={styles.editInput}
                  value={editName}
                  maxLength={120}
                  disabled={editBusy}
                  data-testid="designer-edit-name"
                  onChange={(e) => setEditName(e.target.value)}
                />
              </label>
              <label className={styles.editLabel}>
                Bio
                <textarea
                  className={styles.editTextarea}
                  value={editBio}
                  maxLength={2000}
                  rows={4}
                  disabled={editBusy}
                  data-testid="designer-edit-bio"
                  onChange={(e) => setEditBio(e.target.value)}
                />
              </label>
              <div className={styles.sheetActions}>
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
                <button
                  type="button"
                  className={styles.ghostBtn}
                  disabled={editBusy}
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </button>
                <button type="submit" className={styles.primaryBtn} disabled={editBusy}>
                  {editBusy ? 'Saving…' : 'Save'}
                </button>
              </div>
              {editError ? (
                <p className={styles.status} role="alert">
                  {editError}
                </p>
              ) : null}
            </form>
          </div>
        </div>
      ) : null}

      {previewLook ? (
        <PublishedLookLightbox item={previewLook} onClose={() => setPreviewLook(null)} />
      ) : null}

      {previewAvatar && avatarSrc ? (
        <AvatarPhotoLightbox
          src={avatarSrc}
          name={displayName}
          onClose={() => setPreviewAvatar(false)}
        />
      ) : null}
    </div>
  )
}

function FriendLookTile({ item, onOpen }: { item: GalleryItem; onOpen: () => void }) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  return (
    <button
      type="button"
      className={styles.lookTile}
      data-testid={`friend-look-${item.id}`}
      aria-label={`Open ${item.title || 'published look'}`}
      onClick={onOpen}
    >
      {src ? (
        <img
          src={src}
          alt=""
          className={styles.lookImage}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className={styles.lookPlaceholder} aria-hidden />
      )}
      <span className={styles.lookCaption}>{item.title || 'Untitled look'}</span>
    </button>
  )
}

function PublishedLookLightbox({
  item,
  onClose,
}: {
  item: GalleryItem
  onClose: () => void
}) {
  const titleId = useId()
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  return (
    <div
      className={styles.lookBackdrop}
      role="presentation"
      data-testid="designer-look-preview"
      onClick={onClose}
    >
      <div
        className={styles.lookDialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.lookDialogHead}>
          <div>
            <h2 id={titleId} className={styles.lookDialogTitle}>
              {item.title || 'Untitled look'}
            </h2>
            <p className={styles.lookDialogMeta}>
              {item.likes_count ?? 0} likes
              {item.rating_average != null ? ` · ${item.rating_average.toFixed(1)} score` : ''}
            </p>
          </div>
          <button type="button" className={styles.closeIcon} aria-label="Close look" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        {src ? (
          <img src={src} alt="" className={styles.lookDialogImage} />
        ) : (
          <div className={styles.lookDialogPlaceholder} aria-hidden />
        )}
      </div>
    </div>
  )
}

function AvatarPhotoLightbox({
  src,
  name,
  onClose,
}: {
  src: string
  name: string
  onClose: () => void
}) {
  const titleId = useId()
  return (
    <div
      className={styles.lookBackdrop}
      role="presentation"
      data-testid="designer-avatar-preview-lightbox"
      onClick={onClose}
    >
      <div
        className={styles.avatarDialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.lookDialogHead}>
          <h2 id={titleId} className={styles.lookDialogTitle}>
            {name}
          </h2>
          <button
            type="button"
            className={styles.closeIcon}
            aria-label="Close profile photo"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>
        <img src={src} alt={`${name}'s profile photo`} className={styles.avatarDialogImage} />
      </div>
    </div>
  )
}
