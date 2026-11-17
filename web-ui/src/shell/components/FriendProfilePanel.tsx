import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Camera, Heart, MessageCircle, Star, UserMinus, UserPlus, X } from 'lucide-react'
import { useAuth } from '@/services/auth/AuthProvider'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { ApiError } from '@/services/api/client'
import type { FriendUser } from '@/services/friendsApi'
import {
  getGalleryItem,
  likeGalleryItem,
  listGalleryComments,
  listUserGallery,
  postGalleryComment,
  rateGalleryItem,
  unlikeGalleryItem,
  type GalleryComment,
  type GalleryItem,
} from '@/services/galleryApi'
import { syncFollowStatus } from '@/lib/followStatusStore'
import {
  followCreator,
  getFollowStatus,
  getPublicProfile,
  listProfileFollowers,
  profileAvatarSrc,
  updateMyProfile,
  unfollowCreator,
  uploadMyAvatar,
  type FollowerListItem,
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
  const [followersOpen, setFollowersOpen] = useState(false)
  const [followersState, setFollowersState] = useState<
    | { status: 'idle' }
    | { status: 'loading' }
    | { status: 'error'; message: string }
    | { status: 'ready'; people: FollowerListItem[] }
  >({ status: 'idle' })
  const [followerBusyId, setFollowerBusyId] = useState<string | null>(null)
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const openedEditRef = useRef(false)
  const editTitleId = useId()
  const followersTitleId = useId()
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
    setFollowersOpen(false)
    setFollowersState({ status: 'idle' })
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
        const following = Boolean(follow?.following)
        if (viewerId && viewerId !== friend.user_id) {
          syncFollowStatus(viewerId, friend.user_id, following)
        }
        setState({
          status: 'ready',
          profile,
          looks,
          following,
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
    syncFollowStatus(viewerId, friend.user_id, next)
    try {
      if (next) await followCreator(friend.user_id)
      else await unfollowCreator(friend.user_id)
    } catch {
      setState((prev) => (prev.status === 'ready' ? { ...prev, following: !next } : prev))
      syncFollowStatus(viewerId, friend.user_id, !next)
    } finally {
      setFollowBusy(false)
    }
  }

  const openFollowers = () => {
    if (state.status !== 'ready') return
    setFollowersOpen(true)
    setFollowersState({ status: 'loading' })
    void listProfileFollowers(friend.user_id)
      .then((people) => setFollowersState({ status: 'ready', people }))
      .catch((err: unknown) =>
        setFollowersState({
          status: 'error',
          message: err instanceof ApiError ? err.message : 'Could not load followers.',
        }),
      )
  }

  const onToggleFollowerFollow = async (person: FollowerListItem) => {
    if (!viewerId || person.user_id === viewerId || followerBusyId) return
    const next = !person.following
    setFollowerBusyId(person.user_id)
    setFollowersState((prev) =>
      prev.status === 'ready'
        ? {
            ...prev,
            people: prev.people.map((row) =>
              row.user_id === person.user_id ? { ...row, following: next } : row,
            ),
          }
        : prev,
    )
    syncFollowStatus(viewerId, person.user_id, next)
    try {
      if (next) await followCreator(person.user_id)
      else await unfollowCreator(person.user_id)
    } catch {
      setFollowersState((prev) =>
        prev.status === 'ready'
          ? {
              ...prev,
              people: prev.people.map((row) =>
                row.user_id === person.user_id ? { ...row, following: !next } : row,
              ),
            }
          : prev,
      )
      syncFollowStatus(viewerId, person.user_id, !next)
    } finally {
      setFollowerBusyId(null)
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
      <p className={styles.eyebrow}>FashionRise</p>

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

          {state.status === 'ready' ? (
            <ul className={styles.stats} aria-label="Public stats">
              <li>
                <strong data-testid="friend-published-count">{state.looks.length}</strong>
                <span>Published</span>
              </li>
              {state.profile ? (
                <>
                  <li>
                    <button
                      type="button"
                      className={styles.statBtn}
                      data-testid="designer-followers-btn"
                      aria-haspopup="dialog"
                      onClick={openFollowers}
                    >
                      <strong data-testid="designer-followers">
                        {state.profile.followers_count}
                      </strong>
                      <span>Followers</span>
                    </button>
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
            <h2 className={styles.collectionTitle}>Looks</h2>
            <span className={styles.collectionMeta}>{state.looks.length} published</span>
          </div>
          {state.looks.length === 0 ? (
            <div className={styles.emptyLooksCard} data-testid="friend-looks-empty">
              <p className={styles.emptyLooksTitle}>No looks yet</p>
              <p className={styles.emptyLooks}>
                No published FashionRise looks yet.
              </p>
            </div>
          ) : (
            <ul className={styles.looksGrid}>
              {state.looks.map((item) => (
                <li key={item.id}>
                  <FriendLookTile
                    item={item}
                    onOpen={() => setPreviewLook(item)}
                    onUnavailable={(id) => {
                      setState((prev) => {
                        if (prev.status !== 'ready') return prev
                        return {
                          ...prev,
                          looks: prev.looks.filter((row) => row.id !== id),
                        }
                      })
                      setPreviewLook((cur) => (cur?.id === id ? null : cur))
                    }}
                  />
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
        <PublishedLookLightbox
          item={previewLook}
          viewerId={viewerId}
          onClose={() => setPreviewLook(null)}
          onItemChange={(next) => {
            setPreviewLook(next)
            setState((prev) => {
              if (prev.status !== 'ready') return prev
              return {
                ...prev,
                looks: prev.looks.map((row) => (row.id === next.id ? { ...row, ...next } : row)),
              }
            })
          }}
          onUnavailable={() => {
            const id = previewLook.id
            setPreviewLook(null)
            setState((prev) => {
              if (prev.status !== 'ready') return prev
              return { ...prev, looks: prev.looks.filter((row) => row.id !== id) }
            })
          }}
        />
      ) : null}

      {previewAvatar && avatarSrc ? (
        <AvatarPhotoLightbox
          src={avatarSrc}
          name={displayName}
          onClose={() => setPreviewAvatar(false)}
        />
      ) : null}

      {followersOpen ? (
        <div
          className={styles.lookBackdrop}
          role="presentation"
          data-testid="designer-followers-sheet"
          onClick={() => setFollowersOpen(false)}
        >
          <div
            className={styles.lookDialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby={followersTitleId}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.lookDialogHead}>
              <div>
                <h2 id={followersTitleId} className={styles.lookDialogTitle}>
                  Followers
                </h2>
                <p className={styles.lookDialogMeta}>
                  Follow people who follow {displayName} — they show up on FashionRise too.
                </p>
              </div>
              <button
                type="button"
                className={styles.closeIcon}
                aria-label="Close followers"
                onClick={() => setFollowersOpen(false)}
              >
                <X size={16} />
              </button>
            </div>
            {followersState.status === 'loading' ? (
              <p className={styles.status}>Loading followers…</p>
            ) : null}
            {followersState.status === 'error' ? (
              <p className={styles.status} role="alert">
                {followersState.message}
              </p>
            ) : null}
            {followersState.status === 'ready' && followersState.people.length === 0 ? (
              <p className={styles.status}>No followers yet.</p>
            ) : null}
            {followersState.status === 'ready' && followersState.people.length > 0 ? (
              <ul className={styles.peopleList} data-testid="designer-followers-list">
                {followersState.people.map((person) => {
                  const personAvatar = profileAvatarSrc(person.user_id, person.avatar_url)
                  const canFollow = Boolean(viewerId && viewerId !== person.user_id)
                  return (
                    <li key={person.user_id} className={styles.peopleRow}>
                      <div className={styles.peopleIdentity}>
                        {personAvatar ? (
                          <img
                            src={personAvatar}
                            alt=""
                            className={styles.peopleAvatar}
                          />
                        ) : (
                          <span className={styles.peopleAvatarFallback} aria-hidden>
                            {(person.display_name || person.username || '?').slice(0, 1)}
                          </span>
                        )}
                        <div>
                          <strong>{person.display_name || person.username}</strong>
                          <div className={styles.handle}>@{person.username}</div>
                        </div>
                      </div>
                      {canFollow ? (
                        <button
                          type="button"
                          className={person.following ? styles.peopleFollowOn : styles.peopleFollow}
                          disabled={followerBusyId === person.user_id}
                          data-testid={`follower-follow-${person.user_id}`}
                          onClick={() => void onToggleFollowerFollow(person)}
                        >
                          {person.following ? (
                            <>
                              <UserMinus size={13} aria-hidden />
                              Following
                            </>
                          ) : (
                            <>
                              <UserPlus size={13} aria-hidden />
                              Follow
                            </>
                          )}
                        </button>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function FriendLookTile({
  item,
  onOpen,
  onUnavailable,
}: {
  item: GalleryItem
  onOpen: () => void
  onUnavailable?: (galleryItemId: string) => void
}) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const mediaGone =
    Boolean(item.look_id) && !authImg.loading && !src && Boolean(authImg.error)

  useEffect(() => {
    if (mediaGone) onUnavailable?.(item.id)
  }, [item.id, mediaGone, onUnavailable])

  if (mediaGone) return null

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
  viewerId,
  onClose,
  onItemChange,
  onUnavailable,
}: {
  item: GalleryItem
  viewerId: string | null
  onClose: () => void
  onItemChange: (next: GalleryItem) => void
  onUnavailable: () => void
}) {
  const titleId = useId()
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const mediaGone =
    Boolean(item.look_id) && !authImg.loading && !src && Boolean(authImg.error)
  const isOwn = Boolean(viewerId && item.user_id === viewerId)
  const canReact = Boolean(viewerId) && !isOwn
  const [busy, setBusy] = useState<'like' | 'score' | 'comment' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [comments, setComments] = useState<GalleryComment[] | null>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (mediaGone) onUnavailable()
  }, [mediaGone, onUnavailable])

  useEffect(() => {
    let cancelled = false
    void listGalleryComments(item.id)
      .then((rows) => {
        if (!cancelled) setComments(rows)
      })
      .catch(() => {
        if (!cancelled) setComments([])
      })
    return () => {
      cancelled = true
    }
  }, [item.id])

  const refresh = useCallback(async () => {
    const fresh = await getGalleryItem(item.id)
    onItemChange(fresh)
    return fresh
  }, [item.id, onItemChange])

  const onToggleLike = useCallback(async () => {
    if (!canReact || busy) return
    setBusy('like')
    setActionError(null)
    try {
      if (item.liked_by_me) await unlikeGalleryItem(item.id)
      else await likeGalleryItem(item.id)
      await refresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not update like')
    } finally {
      setBusy(null)
    }
  }, [busy, canReact, item.id, item.liked_by_me, refresh])

  const onScore = useCallback(
    async (value: string) => {
      if (!canReact || busy) return
      const score = Number(value)
      if (!Number.isFinite(score) || score < 1 || score > 10) return
      setBusy('score')
      setActionError(null)
      try {
        await rateGalleryItem(item.id, score)
        await refresh()
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Could not save score')
      } finally {
        setBusy(null)
      }
    },
    [busy, canReact, item.id, refresh],
  )

  const onSendComment = useCallback(async () => {
    const body = draft.trim()
    if (!viewerId || !body || busy) return
    setBusy('comment')
    setActionError(null)
    try {
      const row = await postGalleryComment(item.id, body)
      setComments((prev) => [...(prev ?? []), row])
      setDraft('')
      await refresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not post comment')
    } finally {
      setBusy(null)
    }
  }, [busy, draft, item.id, refresh, viewerId])

  if (mediaGone) return null

  return (
    <div
      className={styles.lookBackdrop}
      role="presentation"
      data-testid="designer-look-preview"
      onClick={onClose}
    >
      <div
        className={`${styles.lookDialog} ${styles.lookDialogSocial}`}
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
              {item.rating_count ? ` · ${item.rating_count} ratings` : ''}
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
        <div className={styles.lookSocialRail} aria-label="Look reactions">
          {canReact ? (
            <button
              type="button"
              className={item.liked_by_me ? styles.lookSocialOn : styles.lookSocialBtn}
              aria-pressed={Boolean(item.liked_by_me)}
              disabled={busy === 'like'}
              onClick={() => void onToggleLike()}
            >
              <Heart size={16} aria-hidden fill={item.liked_by_me ? 'currentColor' : 'none'} />
              {item.likes_count ?? 0}
            </button>
          ) : (
            <span className={styles.lookSocialChip}>
              <Heart size={16} aria-hidden />
              {item.likes_count ?? 0}
            </span>
          )}
          {canReact ? (
            <label className={styles.lookScoreLabel}>
              <Star size={16} aria-hidden />
              <select
                className={styles.lookScoreSelect}
                aria-label="Rate look from 1 to 10"
                value={item.my_score ?? ''}
                disabled={busy === 'score'}
                onChange={(e) => void onScore(e.target.value)}
              >
                <option value="" disabled>
                  {item.my_score ? `Yours ${item.my_score}` : 'Rate'}
                </option>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className={styles.lookSocialChip}>
              <Star size={16} aria-hidden />
              {item.rating_average != null ? item.rating_average.toFixed(1) : '—'}
            </span>
          )}
          <span className={styles.lookSocialChip}>
            <MessageCircle size={16} aria-hidden />
            {comments?.length ?? item.comments_count ?? 0}
          </span>
        </div>
        {actionError ? (
          <p className={styles.status} role="alert">
            {actionError}
          </p>
        ) : null}
        <div className={styles.lookComments}>
          <p className={styles.lookCommentsTitle}>Comments</p>
          {comments == null ? (
            <p className={styles.lookDialogMeta}>Loading…</p>
          ) : comments.length === 0 ? (
            <p className={styles.lookDialogMeta}>Be the first to comment.</p>
          ) : (
            <ul className={styles.lookCommentList}>
              {comments.map((row) => (
                <li key={row.id}>
                  <strong>{row.username ? `@${row.username}` : 'Designer'}</strong>
                  <span>{row.body}</span>
                </li>
              ))}
            </ul>
          )}
          {viewerId ? (
            <div className={styles.lookCommentCompose}>
              <input
                className={styles.lookCommentInput}
                value={draft}
                maxLength={500}
                placeholder="Add a comment…"
                aria-label="Add a comment"
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void onSendComment()
                  }
                }}
              />
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={busy === 'comment' || !draft.trim()}
                onClick={() => void onSendComment()}
              >
                Send
              </button>
            </div>
          ) : null}
        </div>
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
