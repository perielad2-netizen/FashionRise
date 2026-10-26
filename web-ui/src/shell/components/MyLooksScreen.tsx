import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Archive, ArrowLeft, Download, Heart, RefreshCw, Star, X } from 'lucide-react'
import { useAuthJobImage } from '@/hooks/useAuthJobImage'
import { fetchJobImageBlob } from '@/services/ai/magicApi'
import {
  listLooks,
  lookThumbnailJobId,
  updateLook,
  type LookFilter,
  type LookRecord,
} from '@/services/looksApi'
import styles from './MyLooksScreen.module.css'

const DATE_FORMAT = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })
const PAGE_SIZE = 24

type Props = {
  focusLookId?: string | null
  onBackToStudio: () => void
  onFocusConsumed?: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: LookRecord[]; total: number }

function formatDate(iso: string): string {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 'Unknown date' : DATE_FORMAT.format(t)
}

function sideBadges(look: LookRecord): string[] {
  const badges: string[] = []
  if (look.front?.has_image) badges.push('Front')
  if (look.back?.has_image) badges.push('Back')
  if (badges.length === 0 && look.kind === 'dual') badges.push('Dual')
  return badges
}

function LazyLookThumb({ look }: { look: LookRecord }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(false)
  const jobId = lookThumbnailJobId(look)
  useEffect(() => {
    const node = ref.current
    if (!node || visible) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true)
          obs.disconnect()
        }
      },
      { rootMargin: '160px' },
    )
    obs.observe(node)
    return () => obs.disconnect()
  }, [visible])
  const { url, loading } = useAuthJobImage(jobId, visible)
  return (
    <div ref={ref} className={styles.previewWrap}>
      {url ? (
        <img className={styles.previewImg} src={url} alt="" loading="lazy" draggable={false} />
      ) : (
        <div className={styles.previewPending} aria-hidden>
          {loading || !visible ? 'Loading…' : 'Preview unavailable'}
        </div>
      )}
      <div className={styles.badges}>
        {sideBadges(look).map((b) => (
          <span key={b} className={styles.badge}>
            {b}
          </span>
        ))}
      </div>
      {look.is_favorite ? <Star className={styles.favMark} size={16} fill="currentColor" aria-hidden /> : null}
    </div>
  )
}

async function downloadJobImage(jobId: string, filename: string): Promise<void> {
  const blob = await fetchJobImageBlob(jobId)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function LookDetailDialog({
  look,
  onClose,
  onUpdated,
}: {
  look: LookRecord
  onClose: () => void
  onUpdated: (next: LookRecord) => void
}) {
  const titleId = useId()
  const [title, setTitle] = useState(look.title)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mobileSide, setMobileSide] = useState<'front' | 'back'>(
    look.front?.has_image ? 'front' : 'back',
  )
  const frontJob = look.front?.has_image ? look.front.job_id : null
  const backJob = look.back?.has_image ? look.back.job_id : null
  const frontImg = useAuthJobImage(frontJob, true)
  const backImg = useAuthJobImage(backJob, true)
  const notes = look.front?.summary || look.back?.summary || null

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const patch = async (body: Parameters<typeof updateLook>[1]) => {
    setBusy(true)
    setError(null)
    try {
      const next = await updateLook(look.id, body)
      onUpdated(next)
      if (body.title !== undefined) setTitle(next.title)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update look')
    } finally {
      setBusy(false)
    }
  }

  const showBothDesktop = Boolean(frontJob && backJob)
  const dualLike = look.kind === 'dual' || showBothDesktop

  return (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.dialogHead}>
          <div>
            <h2 id={titleId} className={styles.dialogTitle}>
              {look.title}
            </h2>
            <p className={styles.dialogMeta}>{formatDate(look.created_at)}</p>
          </div>
          <button type="button" className={styles.iconBtn} aria-label="Close look details" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className={styles.dialogBody}>
          {dualLike ? (
            <div className={styles.sideSwitch} role="tablist" aria-label="Look side">
              {(['front', 'back'] as const).map((side) => {
                const available = side === 'front' ? Boolean(frontJob) : Boolean(backJob)
                return (
                  <button
                    key={side}
                    type="button"
                    role="tab"
                    aria-selected={mobileSide === side}
                    className={mobileSide === side ? styles.filterActive : styles.filterBtn}
                    disabled={!available}
                    onClick={() => setMobileSide(side)}
                  >
                    {side === 'front' ? 'Front' : 'Back'}
                  </button>
                )
              })}
            </div>
          ) : null}

          <div className={showBothDesktop ? styles.sideGrid : styles.sideGridSingle}>
            {frontJob ? (
              <div
                className={`${styles.sidePane} ${
                  dualLike && mobileSide !== 'front' ? styles.sidePaneHiddenMobile : ''
                }`}
              >
                <span className={styles.sideLabel}>Front</span>
                <div className={styles.sideFrame}>
                  {frontImg.url ? (
                    <img src={frontImg.url} alt={`${look.title} front`} />
                  ) : (
                    <span>{frontImg.loading ? 'Loading…' : 'Unavailable'}</span>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  disabled={!frontImg.url || busy}
                  onClick={() => void downloadJobImage(frontJob, `${look.title}-front.png`)}
                >
                  <Download size={14} aria-hidden />
                  Download front
                </button>
              </div>
            ) : null}
            {backJob ? (
              <div
                className={`${styles.sidePane} ${
                  dualLike && mobileSide !== 'back' ? styles.sidePaneHiddenMobile : ''
                }`}
              >
                <span className={styles.sideLabel}>Back</span>
                <div className={styles.sideFrame}>
                  {backImg.url ? (
                    <img src={backImg.url} alt={`${look.title} back`} />
                  ) : (
                    <span>{backImg.loading ? 'Loading…' : 'Unavailable'}</span>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  disabled={!backImg.url || busy}
                  onClick={() => void downloadJobImage(backJob, `${look.title}-back.png`)}
                >
                  <Download size={14} aria-hidden />
                  Download back
                </button>
              </div>
            ) : null}
          </div>

          {notes ? <p className={styles.notes}>{notes}</p> : null}

          <div className={styles.renameRow}>
            <label className="sr-only" htmlFor={`${titleId}-rename`}>
              Look name
            </label>
            <input
              id={`${titleId}-rename`}
              className={styles.renameInput}
              value={title}
              maxLength={120}
              disabled={busy}
              onChange={(e) => setTitle(e.target.value)}
            />
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={busy || !title.trim() || title.trim() === look.title}
              onClick={() => void patch({ title: title.trim() })}
            >
              Rename
            </button>
          </div>
          {error ? <p className={styles.stateError}>{error}</p> : null}
        </div>

        <div className={styles.dialogActions}>
          <button
            type="button"
            className={look.is_favorite ? styles.iconBtnActive : styles.iconBtn}
            disabled={busy}
            aria-pressed={look.is_favorite}
            onClick={() => void patch({ is_favorite: !look.is_favorite })}
          >
            <Heart size={14} fill={look.is_favorite ? 'currentColor' : 'none'} aria-hidden />
            {look.is_favorite ? 'Favorited' : 'Favorite'}
          </button>
          <button
            type="button"
            className={styles.ghostBtn}
            disabled={busy}
            onClick={() => void patch({ is_archived: !look.is_archived })}
          >
            <Archive size={14} aria-hidden />
            {look.is_archived ? 'Restore' : 'Archive'}
          </button>
          <button type="button" className={styles.primaryBtn} onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export function MyLooksScreen({ focusLookId, onBackToStudio, onFocusConsumed }: Props) {
  const [filter, setFilter] = useState<LookFilter>('all')
  const [query, setQuery] = useState('')
  const [deferredQuery, setDeferredQuery] = useState('')
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [offset, setOffset] = useState(0)
  const [reloadToken, setReloadToken] = useState(0)
  const [selected, setSelected] = useState<LookRecord | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    const t = window.setTimeout(() => setDeferredQuery(query.trim()), 200)
    return () => window.clearTimeout(t)
  }, [query])

  useEffect(() => {
    setOffset(0)
  }, [filter, deferredQuery])

  useEffect(() => {
    const controller = new AbortController()
    setState((prev) => (offset === 0 ? { status: 'loading' } : prev))
    listLooks({
      filter,
      q: deferredQuery || undefined,
      limit: PAGE_SIZE,
      offset,
      signal: controller.signal,
    })
      .then((page) => {
        if (controller.signal.aborted) return
        setState((prev) => {
          if (offset === 0 || prev.status !== 'ready') {
            return { status: 'ready', items: page.items, total: page.total }
          }
          const seen = new Set(prev.items.map((i) => i.id))
          const merged = [...prev.items]
          for (const item of page.items) {
            if (!seen.has(item.id)) merged.push(item)
          }
          return { status: 'ready', items: merged, total: page.total }
        })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          message:
            err instanceof Error && err.message
              ? err.message
              : 'Could not load your looks. Check your connection and try again.',
        })
      })
    return () => controller.abort()
  }, [filter, deferredQuery, offset, reloadToken])

  useEffect(() => {
    if (!focusLookId || state.status !== 'ready') return
    const hit = state.items.find((i) => i.id === focusLookId)
    if (hit) {
      setSelected(hit)
      onFocusConsumed?.()
      return
    }
    // Focus id may be outside first page — still open via list scan after reload.
    if (offset === 0 && state.items.every((i) => i.id !== focusLookId)) {
      void listLooks({ filter: 'all', limit: 100, offset: 0 })
        .then((page) => {
          const found = page.items.find((i) => i.id === focusLookId)
          if (found) setSelected(found)
        })
        .finally(() => onFocusConsumed?.())
    }
  }, [focusLookId, state, offset, onFocusConsumed])

  const refresh = useCallback(() => {
    setOffset(0)
    setReloadToken((v) => v + 1)
  }, [])

  const onUpdated = useCallback((next: LookRecord) => {
    setSelected(next)
    setState((prev) => {
      if (prev.status !== 'ready') return prev
      const items = prev.items.map((i) => (i.id === next.id ? next : i))
      const visible =
        filter === 'archived'
          ? items.filter((i) => i.is_archived)
          : filter === 'favorites'
            ? items.filter((i) => i.is_favorite && !i.is_archived)
            : items.filter((i) => !i.is_archived)
      return { status: 'ready', items: visible, total: visible.length }
    })
    if (filter !== 'archived' && next.is_archived) {
      setSelected(null)
    }
  }, [filter])

  const toggleFavorite = async (look: LookRecord) => {
    setActionError(null)
    try {
      const next = await updateLook(look.id, { is_favorite: !look.is_favorite })
      onUpdated(next)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update favorite')
    }
  }

  const emptyCopy = useMemo(() => {
    if (filter === 'favorites') return 'No favorite looks yet. Heart a look to keep it close.'
    if (filter === 'archived') return 'No archived looks. Archive keeps paid Magic results recoverable.'
    if (deferredQuery) return 'No looks match that name.'
    return 'Finished Magic looks will appear here automatically — no extra save step.'
  }, [filter, deferredQuery])

  return (
    <section className={styles.screen} aria-label="My Looks">
      <div className={styles.head}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>My Looks</h1>
          <p className={styles.subtitle}>
            Your finished Magic illustrations — private, persistent, and ready to revisit.
          </p>
        </div>
        <div className={styles.headActions}>
          <button type="button" className={styles.ghostBtn} onClick={refresh}>
            <RefreshCw size={14} aria-hidden />
            Refresh
          </button>
          <button type="button" className={styles.ghostBtn} onClick={onBackToStudio}>
            <ArrowLeft size={14} aria-hidden />
            Back to Studio
          </button>
        </div>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.filters} role="tablist" aria-label="Look filters">
          {(
            [
              ['all', 'All'],
              ['favorites', 'Favorites'],
              ['archived', 'Archived'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={filter === id}
              className={filter === id ? styles.filterActive : styles.filterBtn}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          type="search"
          placeholder="Search by look name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search looks by name"
        />
      </div>

      <div className={styles.scroll}>
        {actionError ? <p className={styles.stateError}>{actionError}</p> : null}

        {state.status === 'loading' ? (
          <p className={styles.stateMsg} role="status">
            Loading your looks…
          </p>
        ) : null}

        {state.status === 'error' ? (
          <div className={styles.stateError} role="alert">
            <p>{state.message}</p>
            <button type="button" className={styles.primaryBtn} onClick={refresh}>
              Try again
            </button>
          </div>
        ) : null}

        {state.status === 'ready' && state.items.length === 0 ? (
          <div className={styles.stateMsg}>
            <p className={styles.emptyTitle}>No looks here yet</p>
            <p>{emptyCopy}</p>
          </div>
        ) : null}

        {state.status === 'ready' && state.items.length > 0 ? (
          <>
            <ul className={styles.grid} aria-label="My Looks gallery">
              {state.items.map((look) => (
                <li key={look.id} className={styles.card}>
                  <LazyLookThumb look={look} />
                  <div className={styles.cardBody}>
                    <h3 className={styles.cardTitle} title={look.title}>
                      {look.title}
                    </h3>
                    <p className={styles.cardMeta}>{formatDate(look.created_at)}</p>
                    <div className={styles.cardActions}>
                      <button
                        type="button"
                        className={styles.cardOpen}
                        onClick={() => setSelected(look)}
                        aria-label={`View details for ${look.title}`}
                      >
                        View details
                      </button>
                      <button
                        type="button"
                        className={look.is_favorite ? styles.iconBtnActive : styles.iconBtn}
                        aria-label={look.is_favorite ? `Unfavorite ${look.title}` : `Favorite ${look.title}`}
                        aria-pressed={look.is_favorite}
                        onClick={() => void toggleFavorite(look)}
                      >
                        <Heart size={14} fill={look.is_favorite ? 'currentColor' : 'none'} />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {state.items.length < state.total ? (
              <button
                type="button"
                className={`${styles.ghostBtn} ${styles.moreBtn}`}
                onClick={() => setOffset((v) => v + PAGE_SIZE)}
              >
                Load more
              </button>
            ) : null}
          </>
        ) : null}
      </div>

      {selected ? (
        <LookDetailDialog look={selected} onClose={() => setSelected(null)} onUpdated={onUpdated} />
      ) : null}
    </section>
  )
}
