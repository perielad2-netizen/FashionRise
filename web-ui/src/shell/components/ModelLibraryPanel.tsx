import { useMemo, useRef, useState } from 'react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { BUILTIN_MODELS, type ModelChoice } from '@/assets/modelLibrary'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
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

type Props = {
  selected: ModelChoice
  customPreviewUrl: string | null
  onSelect: (choice: ModelChoice) => void
  onCustomFile: (file: File) => void
  /** Create My Croquis wizard entry — only when UI gate is ON. */
  onCreateMyCroquis?: () => void
  /** Overlay gallery on tablet/immersive; sidebar on desktop. */
  variant?: 'sidebar' | 'gallery'
}

export function ModelLibraryPanel({
  selected,
  customPreviewUrl,
  onSelect,
  onCustomFile,
  onCreateMyCroquis,
  variant = 'sidebar',
}: Props) {
  const [filter, setFilter] = useState<Filter>('all')
  const inputRef = useRef<HTMLInputElement>(null)
  const croquisUi = isMyCroquisUiEnabled()

  const cards = useMemo(() => {
    if (filter === 'all') return CARDS
    return CARDS.filter((c) => c.filter === filter || c.filter === 'utility')
  }, [filter])

  return (
    <aside
      className={`${styles.panel} ${variant === 'gallery' ? styles.gallery : ''}`}
      aria-label="Model library"
      data-variant={variant}
    >
      <div className={styles.tabs}>
        <button type="button" className={styles.tabActive} aria-current="page">
          Models
        </button>
        <button
          type="button"
          className={styles.tab}
          disabled
          aria-disabled
          title="My Gallery is coming later"
        >
          My Gallery
          <span className={styles.soon}>Soon</span>
        </button>
      </div>

      {croquisUi && onCreateMyCroquis ? (
        <div className={styles.filters} style={{ marginBottom: '0.35rem' }}>
          <button
            type="button"
            className={styles.filter}
            onClick={onCreateMyCroquis}
            aria-label="Open Create My Croquis wizard"
            data-testid="create-my-croquis-entry"
          >
            Create My Croquis
          </button>
          {selected === 'personal' ? (
            <span className={styles.soon} aria-live="polite">
              Active
            </span>
          ) : null}
        </div>
      ) : null}

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
