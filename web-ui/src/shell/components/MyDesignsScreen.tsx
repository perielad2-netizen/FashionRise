import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, FolderOpen, RefreshCw } from 'lucide-react'
import { PREVIEW_PAGE_SIZE, PreviewRenderer } from '@/lib/designPreview'
import {
  modelLabel,
  type DamagedSavedDesign,
  type SavedDesignRecord,
  type SavedDesignSnapshot,
} from '@/lib/savedDesign'
import type { SaveStatus } from '@/lib/draftDocument'
import type { Stroke } from '@/lib/strokes'
import type { ModelChoice } from '@/shell/modelTypes'
import { listSavedDesigns } from '@/services/savedDesignsApi'
import styles from './MyDesignsScreen.module.css'

type WorkingDraft = {
  strokes: Stroke[]
  model: ModelChoice
  dimmed: boolean
  brush: SavedDesignSnapshot['brush']
  saveStatus: SaveStatus
  saveStatusLabel: string
}

type Props = {
  ownerId: string
  working: WorkingDraft
  libraryVersion: number
  onOpen: (designId: string) => void
  onBackToStudio: () => void
  opening: boolean
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; designs: SavedDesignRecord[]; damaged: DamagedSavedDesign[] }

const DATE_FORMAT = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

function formatDate(iso: string): string {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 'Unknown date' : DATE_FORMAT.format(t)
}

function usePreview(
  renderer: PreviewRenderer | null,
  key: string,
  snapshot: SavedDesignSnapshot,
): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!renderer) return
    let cancelled = false
    void renderer.request(key, snapshot).then((next) => {
      if (!cancelled) setUrl(next)
    })
    return () => {
      cancelled = true
    }
    // Snapshot content is identified by `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderer, key])
  return url
}

function PreviewImage({ url, label }: { url: string | null; label: string }) {
  return (
    <div className={styles.paper}>
      {url ? (
        <img src={url} alt={label} className={styles.previewImg} draggable={false} />
      ) : (
        <span className={styles.previewPending} aria-hidden="true" />
      )}
    </div>
  )
}

function SavedDesignCard({
  record,
  renderer,
  onOpen,
  disabled,
}: {
  record: SavedDesignRecord
  renderer: PreviewRenderer | null
  onOpen: (id: string) => void
  disabled: boolean
}) {
  const url = usePreview(renderer, `saved:${record.id}`, record.snapshot)
  const title = record.title || 'Untitled design'
  return (
    <li className={styles.card}>
      <PreviewImage url={url} label={`Preview of ${title}`} />
      <div className={styles.cardBody}>
        <h3 className={styles.cardTitle} title={title}>
          {title}
        </h3>
        <p className={styles.cardMeta}>
          <span>{formatDate(record.savedAt)}</span>
          <span aria-hidden="true"> · </span>
          <span>{modelLabel(record.snapshot.model)}</span>
        </p>
        <button
          type="button"
          className={styles.openBtn}
          onClick={() => onOpen(record.id)}
          disabled={disabled}
          aria-label={`Open ${title} in Studio`}
        >
          <FolderOpen size={14} aria-hidden="true" />
          Open
        </button>
      </div>
    </li>
  )
}

export function MyDesignsScreen({
  ownerId,
  working,
  libraryVersion,
  onOpen,
  onBackToStudio,
  opening,
}: Props) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [visible, setVisible] = useState(PREVIEW_PAGE_SIZE)
  const [reloadToken, setReloadToken] = useState(0)
  const [renderer] = useState(() => new PreviewRenderer())
  const workingKeyRef = useRef<string | null>(null)

  useEffect(() => () => renderer.dispose(), [renderer])

  useEffect(() => {
    const controller = new AbortController()
    listSavedDesigns(ownerId, controller.signal)
      .then((library) => {
        if (controller.signal.aborted) return
        setState({ status: 'ready', designs: library.designs, damaged: library.damaged })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          message:
            err instanceof Error && err.message
              ? err.message
              : 'Could not load your designs. Check your connection and try again.',
        })
      })
    return () => controller.abort()
  }, [ownerId, libraryVersion, reloadToken])

  const refresh = useCallback(() => {
    setState({ status: 'loading' })
    setReloadToken((v) => v + 1)
  }, [])

  const workingSnapshot = useMemo<SavedDesignSnapshot>(
    () => ({
      strokes: working.strokes,
      model: working.model,
      brush: working.brush,
      dimmed: working.dimmed,
    }),
    [working.strokes, working.model, working.brush, working.dimmed],
  )
  const lastStroke = working.strokes[working.strokes.length - 1]
  const workingKey = `working:${working.strokes.length}:${lastStroke?.id ?? ''}:${working.model}:${working.dimmed}`
  useEffect(() => {
    if (!renderer) return
    const previous = workingKeyRef.current
    workingKeyRef.current = workingKey
    if (previous && previous !== workingKey) renderer.release(previous)
  }, [renderer, workingKey])
  const workingUrl = usePreview(renderer, workingKey, workingSnapshot)

  const designs = state.status === 'ready' ? state.designs : []
  const damaged = state.status === 'ready' ? state.damaged : []

  return (
    <section className={styles.screen} aria-label="My Designs">
      <header className={styles.head}>
        <div>
          <h1 className={styles.title}>My Designs</h1>
          <p className={styles.subtitle}>Private to your account. Only you can see these.</p>
        </div>
        <div className={styles.headActions}>
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={refresh}
            disabled={state.status === 'loading'}
          >
            <RefreshCw size={14} aria-hidden="true" />
            Refresh
          </button>
          <button type="button" className={styles.ghostBtn} onClick={onBackToStudio}>
            <ArrowLeft size={14} aria-hidden="true" />
            Back to Studio
          </button>
        </div>
      </header>

      <div className={styles.scroll}>
        <section className={styles.section} aria-labelledby="my-designs-working">
          <h2 id="my-designs-working" className={styles.sectionTitle}>
            Studio working draft
          </h2>
          <div className={styles.workingCard}>
            <PreviewImage url={workingUrl} label="Preview of your Studio working draft" />
            <div className={styles.cardBody}>
              <h3 className={styles.cardTitle}>Current sketch</h3>
              <p className={styles.cardMeta}>
                <span>{modelLabel(working.model)}</span>
                <span aria-hidden="true"> · </span>
                <span>
                  {working.strokes.length} {working.strokes.length === 1 ? 'stroke' : 'strokes'}
                </span>
              </p>
              <p className={styles.cardStatus}>{working.saveStatusLabel}</p>
              <p className={styles.hint}>
                Autosaves privately. Opening a saved design replaces this sketch after you confirm.
              </p>
              <button type="button" className={styles.openBtn} onClick={onBackToStudio}>
                Continue in Studio
              </button>
            </div>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="my-designs-saved">
          <h2 id="my-designs-saved" className={styles.sectionTitle}>
            Saved designs
            {state.status === 'ready' ? (
              <span className={styles.count}>{designs.length}</span>
            ) : null}
          </h2>

          {state.status === 'loading' ? (
            <p className={styles.stateMsg} role="status">
              Loading your designs…
            </p>
          ) : null}

          {state.status === 'error' ? (
            <div className={styles.stateError} role="alert">
              <p>{state.message}</p>
              <button type="button" className={styles.ghostBtn} onClick={refresh}>
                Try again
              </button>
            </div>
          ) : null}

          {state.status === 'ready' && designs.length === 0 && damaged.length === 0 ? (
            <p className={styles.stateMsg}>
              No saved designs yet. In Studio, choose <strong>Save design</strong> to keep a named
              private copy of your sketch.
            </p>
          ) : null}

          {designs.length > 0 ? (
            <ul className={styles.grid} aria-label="Saved designs">
              {designs.slice(0, visible).map((record) => (
                <SavedDesignCard
                  key={record.id}
                  record={record}
                  renderer={renderer}
                  onOpen={onOpen}
                  disabled={opening}
                />
              ))}
            </ul>
          ) : null}

          {designs.length > visible ? (
            <button
              type="button"
              className={styles.moreBtn}
              onClick={() => setVisible((v) => v + PREVIEW_PAGE_SIZE)}
            >
              Show more ({designs.length - visible} more)
            </button>
          ) : null}

          {damaged.length > 0 ? (
            <div className={styles.damaged} role="note">
              <p>
                {damaged.length === 1
                  ? '1 saved design cannot be shown because its data is damaged or uses an unsupported format.'
                  : `${damaged.length} saved designs cannot be shown because their data is damaged or uses an unsupported format.`}{' '}
                They were not changed.
              </p>
              <ul className={styles.damagedList}>
                {damaged.slice(0, 10).map((d) => (
                  <li key={d.id}>
                    {d.title || 'Untitled design'} · {formatDate(d.createdAt)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      </div>
    </section>
  )
}
