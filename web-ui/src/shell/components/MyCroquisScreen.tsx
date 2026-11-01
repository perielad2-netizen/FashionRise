import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { ArrowLeft, Plus, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import {
  acceptedVersionNumber,
  erasePersonalCroquis,
  fetchCroquisAssetBlob,
  listPersonalCroquis,
  type PersonalCroquisRead,
} from '@/services/personalCroquisApi'
import { ApiError } from '@/services/api/client'
import { CreateMyCroquisWizard } from '@/shell/components/CreateMyCroquisWizard'
import styles from './MyCroquisScreen.module.css'

const DATE_FORMAT = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

type Props = {
  onBackToStudio: () => void
  onUseInStudio: (croquisId: string, version: number) => void
  /** True when the active Studio draft pins this croquis (warn before erase). */
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
}: {
  assetId: string | null
  label: string
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
          {!assetId || failed ? 'Preview unavailable' : visible ? 'Loading…' : ' '}
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
  const deleteInFlightRef = useRef(false)

  const reload = useCallback(() => {
    setReloadToken((n) => n + 1)
  }, [])

  useEffect(() => {
    if (!isMyCroquisUiEnabled()) {
      setState({ status: 'error', message: 'My Croquis is not enabled in this build.' })
      return
    }
    const controller = new AbortController()
    setState({ status: 'loading' })
    listPersonalCroquis(controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return
        const usable = rows.filter((row) => !row.erased && acceptedVersionNumber(row) != null)
        setState({ status: 'ready', items: usable })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          message:
            err instanceof Error && err.message
              ? err.message
              : 'Could not load My Croquis. Check your connection and try again.',
        })
      })
    return () => controller.abort()
  }, [reloadToken, libraryVersion])

  const beginDelete = useCallback(
    (row: PersonalCroquisRead) => {
      const version = acceptedVersionNumber(row)
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
    if (!deleteDialog || deleteDialog.phase === 'error') return
    if (deleteInFlightRef.current) return
    const { row, version, referencedInStudio } = deleteDialog
    deleteInFlightRef.current = true
    setDeleteDialog({ phase: 'deleting', row, version, referencedInStudio })
    try {
      await erasePersonalCroquis(row.id)
      setDeleteDialog(null)
      setNotice(
        referencedInStudio
          ? `Deleted “${row.display_name || 'Untitled croquis'}”. Studio strokes were kept — the underlay may show unavailable until you pick another croquis.`
          : `Deleted “${row.display_name || 'Untitled croquis'}”.`,
      )
      reload()
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error && err.message
            ? err.message
            : 'Could not delete this croquis. Try again.'
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
    (croquisId: string, version: number) => {
      setWizardOpen(false)
      onUseInStudio(croquisId, version)
    },
    [onUseInStudio],
  )

  if (!isMyCroquisUiEnabled()) {
    return (
      <section className={styles.screen} aria-labelledby={titleId}>
        <header className={styles.head}>
          <div className={styles.titleBlock}>
            <h1 id={titleId} className={styles.title}>
              My Croquis
            </h1>
            <p className={styles.subtitle}>Personal croquis library is not enabled in this build.</p>
          </div>
          <button type="button" className={styles.ghostBtn} onClick={onBackToStudio}>
            <ArrowLeft size={14} aria-hidden />
            Back to Studio
          </button>
        </header>
      </section>
    )
  }

  return (
    <section className={styles.screen} aria-labelledby={titleId}>
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <h1 id={titleId} className={styles.title}>
            My Croquis
          </h1>
          <p className={styles.subtitle}>
            Preview, create, and select your private personal croquis for Studio.
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
            disabled={state.status === 'loading'}
            aria-label="Refresh My Croquis"
          >
            <RefreshCw size={14} aria-hidden />
            Refresh
          </button>
          <button
            type="button"
            className={styles.primaryBtn}
            onClick={() => setWizardOpen(true)}
          >
            <Plus size={14} aria-hidden />
            Create New Croquis
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
          <p className={styles.empty}>Loading your croquis…</p>
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
            <p className={styles.empty}>No accepted personal croquis yet.</p>
            <button type="button" className={styles.primaryBtn} onClick={() => setWizardOpen(true)}>
              <Plus size={14} aria-hidden />
              Create New Croquis
            </button>
          </div>
        ) : null}

        {state.status === 'ready' && state.items.length > 0 ? (
          <ul className={styles.grid}>
            {state.items.map((row) => {
              const version = acceptedVersionNumber(row)!
              const assetId = row.latest_accepted_version?.generated_asset_id ?? null
              const title = row.display_name?.trim() || 'Untitled croquis'
              const active = activeStudioPinId === row.id
              return (
                <li key={row.id} className={styles.card}>
                  <CroquisThumb assetId={assetId} label={`Preview of ${title}`} />
                  <div className={styles.cardBody}>
                    <h2 className={styles.cardTitle} title={title}>
                      {title}
                      {active ? <span className={styles.activeBadge}>In Studio</span> : null}
                    </h2>
                    <p className={styles.cardMeta}>
                      <span>v{version}</span>
                      <span aria-hidden="true"> · </span>
                      <span>{formatDate(row.updated_at || row.created_at)}</span>
                    </p>
                    <div className={styles.cardActions}>
                      <button
                        type="button"
                        className={styles.openBtn}
                        onClick={() => onUseInStudio(row.id, version)}
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
          onClose={() => setWizardOpen(false)}
          onPinAccepted={onPinAccepted}
        />
      ) : null}

      {deleteDialog ? (
        <ConfirmDialog
          title={
            deleteDialog.phase === 'error'
              ? 'Could not delete croquis'
              : 'Delete personal croquis?'
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
                <strong>{deleteDialog.row.display_name || 'Untitled croquis'}</strong> and its
                private photo assets? This cannot be undone.
              </p>
              {deleteDialog.referencedInStudio ? (
                <p>
                  Studio currently uses this croquis. Your drawing strokes stay on the canvas; the
                  underlay will become unavailable until you select another croquis. Unrelated
                  drawings and designs are not deleted.
                </p>
              ) : (
                <p>
                  Studio drawings that pin this croquis will keep their strokes; only the private
                  croquis media is removed. Other designs and looks are not erased.
                </p>
              )}
            </>
          )}
        </ConfirmDialog>
      ) : null}
    </section>
  )
}
