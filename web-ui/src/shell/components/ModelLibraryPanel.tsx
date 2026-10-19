import { useMemo, useRef, useState } from 'react'
import { UI_ASSETS } from '@/assets/uiAssets'
import type { ModelChoice, ModelLibraryCard } from '@/shell/modelTypes'
import styles from './ModelLibraryPanel.module.css'

const CARDS: ModelLibraryCard[] = [
  {
    id: 'female',
    label: 'Female',
    src: UI_ASSETS.model.female,
    filter: 'female',
    kind: 'production',
    choice: 'female',
  },
  {
    id: 'male',
    label: 'Male',
    src: UI_ASSETS.model.male,
    filter: 'male',
    kind: 'production',
    choice: 'male',
  },
  {
    id: 'custom',
    label: 'Custom',
    src: UI_ASSETS.model.custom,
    filter: 'utility',
    kind: 'production',
    choice: 'custom',
  },
  {
    id: 'blank',
    label: 'Blank',
    src: UI_ASSETS.model.blank,
    filter: 'utility',
    kind: 'production',
    choice: 'blank',
  },
  {
    id: 'ph-f1',
    label: 'Pose A',
    src: '/assets/ui/design-lab/models/croquis-female-01.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-f2',
    label: 'Pose B',
    src: '/assets/ui/design-lab/models/croquis-female-02.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-m1',
    label: 'Pose E',
    src: '/assets/ui/design-lab/models/croquis-male-01.png',
    filter: 'male',
    kind: 'placeholder',
  },
]

type Filter = 'all' | 'female' | 'male'

type Props = {
  selected: ModelChoice
  customPreviewUrl: string | null
  onSelect: (choice: ModelChoice) => void
  onCustomFile: (file: File) => void
}

export function ModelLibraryPanel({
  selected,
  customPreviewUrl,
  onSelect,
  onCustomFile,
}: Props) {
  const [tab, setTab] = useState<'models' | 'gallery'>('models')
  const [filter, setFilter] = useState<Filter>('all')
  const inputRef = useRef<HTMLInputElement>(null)

  const cards = useMemo(() => {
    if (filter === 'all') return CARDS
    return CARDS.filter((c) => c.filter === filter || c.filter === 'utility')
  }, [filter])

  return (
    <aside className={styles.panel} aria-label="Model library">
      <div className={styles.tabs}>
        <button
          type="button"
          className={tab === 'models' ? styles.tabActive : styles.tab}
          onClick={() => setTab('models')}
        >
          Models
        </button>
        <button
          type="button"
          className={tab === 'gallery' ? styles.tabActive : styles.tab}
          onClick={() => setTab('gallery')}
          title="Coming later"
        >
          My Gallery
        </button>
      </div>

      <div className={styles.filters}>
        {(['all', 'female', 'male'] as const).map((id) => (
          <button
            key={id}
            type="button"
            className={filter === id ? styles.filterActive : styles.filter}
            onClick={() => setFilter(id)}
          >
            {id === 'all' ? 'All' : id === 'female' ? 'Female' : 'Male'}
          </button>
        ))}
      </div>

      {tab === 'gallery' ? (
        <p className={styles.note}>My Gallery is coming later.</p>
      ) : (
        <div className={styles.grid}>
          {cards.map((card) => {
            const isSelected = card.choice === selected
            const previewSrc =
              card.choice === 'custom' && customPreviewUrl ? customPreviewUrl : card.src
            const disabled = card.kind === 'placeholder'
            return (
              <button
                key={card.id}
                type="button"
                className={isSelected ? styles.cardSelected : styles.card}
                disabled={disabled}
                aria-disabled={disabled}
                aria-pressed={isSelected}
                aria-label={
                  disabled ? `${card.label} unavailable` : `Select ${card.label} reference`
                }
                title={disabled ? 'Unavailable placeholder' : card.label}
                onClick={() => {
                  if (disabled || !card.choice) return
                  if (card.choice === 'custom') {
                    inputRef.current?.click()
                    return
                  }
                  onSelect(card.choice)
                }}
              >
                <img src={previewSrc} alt="" className={styles.thumb} draggable={false} />
                {disabled ? <span className={styles.badge}>Unavailable</span> : null}
                {!disabled ? <span className={styles.cardLabel}>{card.label}</span> : null}
              </button>
            )
          })}
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
