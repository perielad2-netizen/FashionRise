import { useEffect, useMemo, useRef, useState } from 'react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { BUILTIN_MODELS, type ModelChoice } from '@/assets/modelLibrary'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import {
  acceptedVersionNumber,
  fetchCroquisAssetBlob,
  listPersonalCroquis,
  type PersonalCroquisRead,
} from '@/services/personalCroquisApi'
import type { ModelLibraryCard } from '@/shell/modelTypes'
import styles from './ModelLibraryPanel.module.css'

const UTILITY_CARDS: ModelLibraryCard[] = [
  {
    id: 'custom',
    label: 'Custom',
    pose: 'Upload',
    src: UI_ASSETS.model.custom,
    filter: 'utility',
    choice: 'custom',
  },
  {
    id: 'blank',
    label: 'Blank',
    pose: 'Paper',
    src: UI_ASSETS.model.blank,
    filter: 'utility',
    choice: 'blank',
  },
]

const BUILTIN_CARDS: ModelLibraryCard[] = BUILTIN_MODELS.map((m) => ({
  id: m.id,
  label: m.label,
  pose: m.pose,
  src: m.cardSrc,
  filter: m.gender,
  choice: m.id,
}))

const CARDS: ModelLibraryCard[] = [...BUILTIN_CARDS, ...UTILITY_CARDS]

type Filter = 'all' | 'female' | 'male'
type LibraryTab = 'system' | 'mine'

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: PersonalCroquisRead[] }

type Props = {
  selected: ModelChoice
  customPreviewUrl: string | null
  onSelect: (choice: ModelChoice) => void
  onCustomFile: (file: File) => void
  /** Create Model wizard entry — only when UI gate is ON. */
  onCreateMyCroquis?: () => void
  /** Pin an accepted personal model into Studio. */
  onSelectPersonal?: (croquisId: string, version: number) => void
  /** Currently pinned personal model id (highlights the card). */
  personalCroquisId?: string | null
  /** Overlay gallery on tablet/immersive; sidebar on desktop. */
  variant?: 'sidebar' | 'gallery'
}

function PersonalThumb({ assetId, label }: { assetId: string | null; label: string }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(false)
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const node = ref.current
    if (!node || visible) return
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true)
      return
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true)
          obs.disconnect()
        }
      },
      { rootMargin: '120px' },
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
      })
      .catch(() => {
        if (!cancelled) setUrl(null)
      })
    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [visible, assetId])

  return (
    <div ref={ref} className={styles.personalThumb}>
      {url ? (
        <img src={url} alt={label} className={styles.thumb} draggable={false} />
      ) : (
        <div className={styles.personalPending} aria-hidden>
          {assetId ? '…' : '—'}
        </div>
      )}
    </div>
  )
}

export function ModelLibraryPanel({
  selected,
  customPreviewUrl,
  onSelect,
  onCustomFile,
  onCreateMyCroquis,
  onSelectPersonal,
  personalCroquisId = null,
  variant = 'sidebar',
}: Props) {
  const [filter, setFilter] = useState<Filter>('all')
  const [tab, setTab] = useState<LibraryTab>('system')
  const [mine, setMine] = useState<LoadState>({ status: 'idle' })
  const [reloadToken, setReloadToken] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const croquisUi = isMyCroquisUiEnabled()

  const cards = useMemo(() => {
    if (filter === 'all') return CARDS
    return CARDS.filter((c) => c.filter === filter || c.filter === 'utility')
  }, [filter])

  useEffect(() => {
    if (!croquisUi || tab !== 'mine') return
    const controller = new AbortController()
    setMine({ status: 'loading' })
    listPersonalCroquis(controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return
        const usable = rows.filter((row) => !row.erased && acceptedVersionNumber(row) != null)
        setMine({ status: 'ready', items: usable })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setMine({
          status: 'error',
          message:
            err instanceof Error && err.message
              ? err.message
              : 'Could not load your models. Check your connection and try again.',
        })
      })
    return () => controller.abort()
  }, [croquisUi, tab, reloadToken])

  return (
    <aside
      className={`${styles.panel} ${variant === 'gallery' ? styles.gallery : ''}`}
      aria-label="Model library"
      data-variant={variant}
    >
      <div className={styles.tabs} role="tablist" aria-label="Model library sections">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'system'}
          className={tab === 'system' ? styles.tabActive : styles.tab}
          onClick={() => setTab('system')}
          data-testid="models-tab-system"
        >
          Models
        </button>
        {croquisUi ? (
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'mine'}
            className={tab === 'mine' ? styles.tabActive : styles.tab}
            onClick={() => setTab('mine')}
            data-testid="models-tab-mine"
          >
            My Models
          </button>
        ) : null}
      </div>

      {tab === 'system' ? (
        <>
          <div className={styles.filters} role="tablist" aria-label="Model filters">
            {(['all', 'female', 'male'] as const).map((id) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={filter === id}
                className={filter === id ? styles.filterActive : styles.filter}
                onClick={() => setFilter(id)}
              >
                {id === 'all' ? 'All' : id === 'female' ? 'Female' : 'Male'}
              </button>
            ))}
          </div>

          <div className={styles.grid}>
            {cards.map((card) => {
              const isSelected = card.choice === selected
              const previewSrc =
                card.choice === 'custom' && customPreviewUrl ? customPreviewUrl : card.src
              const title = card.pose ? `${card.label} · ${card.pose}` : card.label
              return (
                <button
                  key={card.id}
                  type="button"
                  className={isSelected ? styles.cardSelected : styles.card}
                  aria-pressed={isSelected}
                  aria-label={`Select ${title} reference`}
                  title={title}
                  onClick={() => {
                    if (card.choice === 'custom') {
                      inputRef.current?.click()
                      return
                    }
                    onSelect(card.choice)
                  }}
                >
                  <img src={previewSrc} alt="" className={styles.thumb} draggable={false} />
                  <span className={styles.cardLabel}>
                    <span className={styles.cardTitle}>{card.label}</span>
                    {card.pose ? <span className={styles.cardPose}>{card.pose}</span> : null}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      ) : (
        <div className={styles.minePane} data-testid="my-models-pane">
          {croquisUi && onCreateMyCroquis ? (
            <button
              type="button"
              className={styles.createMineBtn}
              onClick={onCreateMyCroquis}
              aria-label="Create a personal model"
              data-testid="create-my-croquis-entry"
            >
              Create Model
            </button>
          ) : null}

          {mine.status === 'loading' || mine.status === 'idle' ? (
            <p className={styles.mineStatus}>Loading your models…</p>
          ) : null}

          {mine.status === 'error' ? (
            <div className={styles.mineEmpty}>
              <p className={styles.mineStatus}>{mine.message}</p>
              <button
                type="button"
                className={styles.filter}
                onClick={() => setReloadToken((n) => n + 1)}
              >
                Try again
              </button>
            </div>
          ) : null}

          {mine.status === 'ready' && mine.items.length === 0 ? (
            <div className={styles.mineEmpty} data-testid="my-models-empty">
              <p className={styles.mineEmptyTitle}>Your model library is empty</p>
              <p className={styles.mineStatus}>
                Create a personal model from your photo to sketch on a figure that matches you.
              </p>
              {onCreateMyCroquis ? (
                <button
                  type="button"
                  className={styles.createMineBtn}
                  onClick={onCreateMyCroquis}
                  data-testid="my-models-empty-create"
                >
                  Create Model
                </button>
              ) : null}
            </div>
          ) : null}

          {mine.status === 'ready' && mine.items.length > 0 ? (
            <div className={styles.grid}>
              {mine.items.map((row) => {
                const version = acceptedVersionNumber(row)!
                const assetId = row.latest_accepted_version?.generated_asset_id ?? null
                const title = row.display_name?.trim() || 'Untitled model'
                const isSelected = selected === 'personal' && personalCroquisId === row.id
                return (
                  <button
                    key={row.id}
                    type="button"
                    className={isSelected ? styles.cardSelected : styles.card}
                    aria-pressed={isSelected}
                    aria-label={`Use ${title} in Studio`}
                    title={title}
                    onClick={() => onSelectPersonal?.(row.id, version)}
                  >
                    <PersonalThumb assetId={assetId} label={`Preview of ${title}`} />
                    <span className={styles.cardLabel}>
                      <span className={styles.cardTitle}>{title}</span>
                      <span className={styles.cardPose}>
                        {isSelected ? 'In Studio' : `v${version}`}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className={styles.file}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onCustomFile(file)
          e.target.value = ''
        }}
      />
    </aside>
  )
}
