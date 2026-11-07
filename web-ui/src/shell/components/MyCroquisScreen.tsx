import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { ArrowLeft, Plus, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import {
  acceptPersonalCroquisVersion,
  acceptedVersionNumber,
  erasePersonalCroquis,
  fetchCroquisAssetBlob,
  isMyModelsVisible,
  listPersonalCroquis,
  openVersionSummary,
  rejectPersonalCroquisVersion,
  type PersonalCroquisRead,
} from '@/services/personalCroquisApi'
import { ApiError } from '@/services/api/client'
import { CreateMyCroquisWizard } from '@/shell/components/CreateMyCroquisWizard'
import styles from './MyCroquisScreen.module.css'

const DATE_FORMAT = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

type Props = {
  onBackToStudio: () => void
  onUseInStudio: (croquisId: string, version: number) => void
  /** True when the active Studio draft pins this model (warn before erase). */
  activeStudioPinId?: string | null
  libraryVersion?: number
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: PersonalCroquisRead[] }

type DeleteDialog =
  | { phase: 'confirm'; row: PersonalCroquisRead; version: number; referencedInStudio: boolean }
  | { phase: 'deleting'; row: PersonalCroquisRead; version: number; referencedInStudio: boolean }
  | {
      phase: 'error'
      row: PersonalCroquisRead
      version: number
      referencedInStudio: boolean
      message: string
      canRetry: boolean
    }

function formatDate(iso: string): string {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 'Unknown date' : DATE_FORMAT.format(t)
}

function CroquisThumb({
  assetId,
  label,
  pendingLabel,
}: {
  assetId: string | null
  label: string
  pendingLabel?: string
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(false)
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

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

  useEffect(() => {
    if (!visible || !assetId) return
    let cancelled = false
    let objectUrl: string | null = null
    const controller = new AbortController()
    void fetchCroquisAssetBlob(assetId, controller.signal)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
        setFailed(false)
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true)
          setUrl(null)
        }
      })
    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [visible, assetId])

  return (
    <div ref={ref} className={styles.previewWrap}>
      {url ? (
        <img className={styles.previewImg} src={url} alt={label} loading="lazy" draggable={false} />
      ) : (
        <div className={styles.previewPending} aria-hidden>
          {!assetId || failed
            ? pendingLabel || 'Preview unavailable'
            : visible
              ? 'Loading…'
              : ' '}
        </div>
      )}
    </div>
  )
}

export function MyCroquisScreen({
  onBackToStudio,
  onUseInStudio,
  activeStudioPinId = null,
  libraryVersion = 0,
}: Props) {
  const titleId = useId()
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [reloadToken, setReloadToken] = useState(0)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialog | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reviewBusyId, setReviewBusyId] = useState<string | null>(null)
  const deleteInFlightRef = useRef(false)

  const reload = useCallback(() => {
    setReloadToken((n) => n + 1)
  }, [])

  useEffect(() => {
    if (!isMyCroquisUiEnabled()) {
      setState({ status: 'error', message: 'My Models is not enabled in this build.' })
      return
    }
    const controller = new AbortController()
    setState({ status: 'loading' })
    listPersonalCroquis(controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return
        const usable = rows.filter(isMyModelsVisible)
        setState({ status: 'ready', items: usable })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          message:
            err instanceof Error && err.message
              ? err.message
              : 'Could not load My Models. Check your connection and try again.',
        })
      })
    return () => controller.abort()
  }, [reloadToken, libraryVersion])

  // Soft-poll while any model is still generating so Refresh is not required.
  useEffect(() => {
    if (state.status !== 'ready') return
    const generating = state.items.some((row) => {
      const open = openVersionSummary(row)
      const status = (open?.status || '').toLowerCase()
      return status === 'generating' || status === 'queued'
    })
    if (!generating) return
    const timer = window.setTimeout(() => reload(), 4000)
    return () => window.clearTimeout(timer)
  }, [state, reload])

  const beginDelete = useCallback(
    (row: PersonalCroquisRead) => {
      const version = acceptedVersionNumber(row) ?? openVersionSummary(row)?.version
      if (version == null) return
      setNotice(null)
      setDeleteDialog({
        phase: 'confirm',
        row,
        version,
        referencedInStudio: activeStudioPinId === row.id,
      })
    },
    [activeStudioPinId],
  )

  const confirmDelete = useCallback(async () => {
    // Allow Retry delete after an API error (phase === 'error' with canRetry).
    if (!deleteDialog) return
    if (deleteDialog.phase === 'error' && !deleteDialog.canRetry) return
    if (deleteInFlightRef.current) return
    const { row, version, referencedInStudio } = deleteDialog
    deleteInFlightRef.current = true
    setDeleteDialog({ phase: 'deleting', row, version, referencedInStudio })
    try {
      await erasePersonalCroquis(row.id)
      setDeleteDialog(null)
      setNotice(
        referencedInStudio
          ? `Deleted “${row.display_name || 'Untitled model'}”. Studio strokes were kept — the underlay may show unavailable until you pick another model.`
          : `Deleted “${row.display_name || 'Untitled model'}”.`,
      )
      reload()
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error && err.message
            ? err.message
            : 'Could not delete this model. Try again.'
      setDeleteDialog({
        phase: 'error',
        row,
        version,
        referencedInStudio,
        message,
        canRetry: !(err instanceof ApiError && err.status === 404),
      })
    } finally {
      deleteInFlightRef.current = false
    }
  }, [deleteDialog, reload])

  const onPinAccepted = useCallback(
    (_croquisId: string, _version: number) => {
      // Stay on My Models gallery after Create New so the owner can preview
      // and choose Use in Studio explicitly (#154). Do not auto-navigate away.
      setWizardOpen(false)
      setNotice('New model ready — preview it here, then Use in Studio when you want.')
      reload()
    },
    [reload],
  )

  const runAcceptOpen = useCallback(
    async (row: PersonalCroquisRead) => {
      const open = openVersionSummary(row)
      if (!open || open.status !== 'awaiting_review') return
      setReviewBusyId(row.id)
      setNotice(null)
      try {
        await acceptPersonalCroquisVersion(row.id, open.version)
        setNotice('Model accepted — Use in Studio when you want.')
        reload()
      } catch (err) {
        setNotice(
          err instanceof ApiError
            ? err.message
            : err instanceof Error && err.message
              ? err.message
              : 'Could not accept this model. Try again.',
        )
      } finally {
        setReviewBusyId(null)
      }
    },
    [reload],
  )

  const runRejectOpen = useCallback(
    async (row: PersonalCroquisRead) => {
      const open = openVersionSummary(row)
      if (!open || open.status !== 'awaiting_review') return
      setReviewBusyId(row.id)
      setNotice(null)
      try {
        await rejectPersonalCroquisVersion(row.id, open.version)
        setNotice('Generation discarded. You can Create Model again.')
        reload()
      } catch (err) {
        setNotice(
          err instanceof ApiError
            ? err.message
            : err instanceof Error && err.message
              ? err.message
              : 'Could not discard this model. Try again.',
        )
      } finally {
        setReviewBusyId(null)
      }
    },
    [reload],
  )

  if (!isMyCroquisUiEnabled()) {
    return (
      <section className={styles.screen} aria-labelledby={titleId}>
        <header className={styles.head}>
          <div className={styles.titleBlock}>
            <h1 id={titleId} className={styles.title}>
              My Models
            </h1>
            <p className={styles.subtitle}>Personal model library is not enabled in this build.</p>
          </div>
          <button type="button" className={styles.ghostBtn} onClick={onBackToStudio}>
            <ArrowLeft size={14} aria-hidden />
            Back to Studio
          </button>
        </header>
      </section>
    )
  }

  const refreshing = state.status === 'loading'

  return (
    <section className={styles.screen} aria-labelledby={titleId}>
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <h1 id={titleId} className={styles.title}>
            My Models
          </h1>
          <p className={styles.subtitle}>
            Preview, create, and select your private personal model for Studio.
          </p>
        </div>
        <div className={styles.headActions}>
          <button type="button" className={styles.ghostBtn} onClick={onBackToStudio}>
            <ArrowLeft size={14} aria-hidden />
            Back to Studio
          </button>
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={reload}
            disabled={refreshing}
            aria-label="Refresh My Models"
            aria-busy={refreshing}
          >
            <RefreshCw
              size={14}
              aria-hidden
              className={refreshing ? styles.refreshSpin : undefined}
            />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            type="button"
            className={styles.primaryBtn}
            onClick={() => setWizardOpen(true)}
          >
            <Plus size={14} aria-hidden />
            Create Model
          </button>
        </div>
      </header>

      <div className={styles.scroll}>
        {notice ? (
          <p className={styles.notice} role="status">
            {notice}
          </p>
        ) : null}

        {state.status === 'loading' ? (
          <p className={styles.empty} role="status" aria-live="polite">
            Loading your models…
          </p>
        ) : null}

        {state.status === 'error' ? (
          <div className={styles.emptyBlock}>
            <p className={styles.empty}>{state.message}</p>
            <button type="button" className={styles.ghostBtn} onClick={reload}>
              Try again
            </button>
          </div>
        ) : null}

        {state.status === 'ready' && state.items.length === 0 ? (
          <div className={styles.emptyBlock}>
            <p className={styles.empty}>No personal model yet.</p>
            <button type="button" className={styles.primaryBtn} onClick={() => setWizardOpen(true)}>
              <Plus size={14} aria-hidden />
              Create Model
            </button>
          </div>
        ) : null}

        {state.status === 'ready' && state.items.length > 0 ? (
          <ul className={styles.grid}>
            {state.items.map((row) => {
              const open = openVersionSummary(row)
              const openStatus = (open?.status || '').toLowerCase()
              const accepted = acceptedVersionNumber(row)
              const title = row.display_name?.trim() || 'Untitled model'
              const active = activeStudioPinId === row.id
              const reviewBusy = reviewBusyId === row.id

              if (openStatus === 'generating' || openStatus === 'queued') {
                return (
                  <li key={row.id} className={styles.card}>
                    <CroquisThumb
                      assetId={null}
                      label={`Generating ${title}`}
                      pendingLabel="Generating…"
                    />
                    <div className={styles.cardBody}>
                      <h2 className={styles.cardTitle} title={title}>
                        {title}
                        <span className={`${styles.statusBadge} ${styles.statusBadgeGenerating}`}>
                          Generating
                        </span>
                      </h2>
                      <p className={styles.cardMeta}>
                        <span>v{open!.version}</span>
                        <span aria-hidden="true"> · </span>
                        <span>Working in the background — this page refreshes automatically.</span>
                      </p>
                      <div className={styles.cardActions}>
                        <button
                          type="button"
                          className={styles.ghostBtn}
                          onClick={reload}
                          aria-label={`Refresh status for ${title}`}
                        >
                          <RefreshCw size={14} aria-hidden className={styles.refreshSpin} />
                          Check status
                        </button>
                      </div>
                    </div>
                  </li>
                )
              }

              if (openStatus === 'awaiting_review') {
                return (
                  <li key={row.id} className={styles.card}>
                    <CroquisThumb
                      assetId={open?.generated_asset_id ?? null}
                      label={`Review preview of ${title}`}
                    />
                    <div className={styles.cardBody}>
                      <h2 className={styles.cardTitle} title={title}>
                        {title}
                        <span className={`${styles.statusBadge} ${styles.statusBadgeReview}`}>
                          Ready to review
                        </span>
                      </h2>
                      <p className={styles.cardMeta}>
                        <span>v{open!.version}</span>
                        <span aria-hidden="true"> · </span>
                        <span>{formatDate(row.updated_at || row.created_at)}</span>
                      </p>
                      <div className={styles.cardActions}>
                        <button
                          type="button"
                          className={styles.openBtn}
                          disabled={reviewBusy}
                          onClick={() => void runAcceptOpen(row)}
                          aria-label={`Accept ${title}`}
                        >
                          <Sparkles size={14} aria-hidden />
                          {reviewBusy ? 'Saving…' : 'Accept'}
                        </button>
                        <button
                          type="button"
                          className={styles.deleteBtn}
                          disabled={reviewBusy}
                          onClick={() => void runRejectOpen(row)}
                          aria-label={`Discard ${title}`}
                        >
                          Discard
                        </button>
                      </div>
                    </div>
                  </li>
                )
              }

              if (openStatus === 'reconciliation_required') {
                return (
                  <li key={row.id} className={styles.card}>
                    <CroquisThumb
                      assetId={null}
                      label={`Held review for ${title}`}
                      pendingLabel="Held for review"
                    />
                    <div className={styles.cardBody}>
                      <h2 className={styles.cardTitle} title={title}>
                        {title}
                        <span className={styles.statusBadge}>Held</span>
                      </h2>
                      <p className={styles.cardMeta}>
                        Provider outcome is unknown. This attempt is held — no extra Stars were
                        charged for a retry.
                      </p>
                    </div>
                  </li>
                )
              }

              if (accepted == null) return null
              const assetId = row.latest_accepted_version?.generated_asset_id ?? null
              return (
                <li key={row.id} className={styles.card}>
                  <CroquisThumb assetId={assetId} label={`Preview of ${title}`} />
                  <div className={styles.cardBody}>
                    <h2 className={styles.cardTitle} title={title}>
                      {title}
                      {active ? <span className={styles.activeBadge}>In Studio</span> : null}
                    </h2>
                    <p className={styles.cardMeta}>
                      <span>v{accepted}</span>
                      <span aria-hidden="true"> · </span>
                      <span>{formatDate(row.updated_at || row.created_at)}</span>
                    </p>
                    <div className={styles.cardActions}>
                      <button
                        type="button"
                        className={styles.openBtn}
                        onClick={() => onUseInStudio(row.id, accepted)}
                        aria-label={`Use ${title} in Studio`}
                      >
                        <Sparkles size={14} aria-hidden />
                        Use in Studio
                      </button>
                      <button
                        type="button"
                        className={styles.deleteBtn}
                        onClick={() => beginDelete(row)}
                        aria-label={`Delete ${title}`}
                      >
                        <Trash2 size={14} aria-hidden />
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        ) : null}
      </div>

      {wizardOpen ? (
        <CreateMyCroquisWizard
          open
          onClose={() => {
            setWizardOpen(false)
            reload()
          }}
          onPinAccepted={onPinAccepted}
        />
      ) : null}

      {deleteDialog ? (
        <ConfirmDialog
          title={
            deleteDialog.phase === 'error'
              ? 'Could not delete model'
              : 'Delete personal model?'
          }
          actions={
            deleteDialog.phase === 'error'
              ? [
                  {
                    label: 'Close',
                    onClick: () => setDeleteDialog(null),
                    variant: 'ghost',
                  },
                  ...(deleteDialog.canRetry
                    ? [
                        {
                          label: 'Retry delete',
                          onClick: () => void confirmDelete(),
                          variant: 'danger' as const,
                        },
                      ]
                    : []),
                ]
              : [
                  {
                    label: 'Cancel',
                    onClick: () => setDeleteDialog(null),
                    variant: 'ghost',
                    disabled: deleteDialog.phase === 'deleting',
                  },
                  {
                    label: deleteDialog.phase === 'deleting' ? 'Deleting…' : 'Delete permanently',
                    onClick: () => void confirmDelete(),
                    variant: 'danger',
                    disabled: deleteDialog.phase === 'deleting',
                  },
                ]
          }
        >
          {deleteDialog.phase === 'error' ? (
            <p>{deleteDialog.message}</p>
          ) : (
            <>
              <p>
                Permanently erase{' '}
                <strong>{deleteDialog.row.display_name || 'Untitled model'}</strong> and its
                private photo assets? This cannot be undone.
              </p>
              {deleteDialog.referencedInStudio ? (
                <p>
                  Studio currently uses this model. Your drawing strokes stay on the canvas; the
                  underlay will become unavailable until you select another model. Unrelated
                  drawings and designs are not deleted.
                </p>
              ) : (
                <p>
                  Studio drawings that pin this model will keep their strokes; only the private
                  model media is removed. Other designs and looks are not erased.
                </p>
              )}
            </>
          )}
        </ConfirmDialog>
      ) : null}
    </section>
  )
}
