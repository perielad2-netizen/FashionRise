import { useMemo, useState } from 'react'
import { DESIGN_LAB_MODELS } from '@/design-lab/designLabAssets'
import styles from './ModelLibraryPanel.module.css'

type Filter = 'all' | 'female' | 'male'

export function ModelLibraryPanel() {
  const [tab, setTab] = useState<'models' | 'gallery'>('models')
  const [filter, setFilter] = useState<Filter>('female')
  const [selected, setSelected] = useState('prod-female')

  const cards = useMemo(() => {
    if (filter === 'all') return DESIGN_LAB_MODELS
    return DESIGN_LAB_MODELS.filter((m) => m.filter === filter)
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
        <p className={styles.note}>
          Gallery is a visual prototype here. Production gallery is not connected.
        </p>
      ) : (
        <>
          <div className={styles.grid}>
            {cards.map((card) => (
              <button
                key={card.id}
                type="button"
                className={selected === card.id ? styles.cardSelected : styles.card}
                onClick={() => setSelected(card.id)}
                aria-pressed={selected === card.id}
                aria-label={`${card.label}${card.kind === 'placeholder' ? ' placeholder' : ''}`}
              >
                <img src={card.src} alt="" className={styles.thumb} draggable={false} />
                {card.kind === 'placeholder' ? (
                  <span className={styles.badge}>Placeholder</span>
                ) : null}
              </button>
            ))}
          </div>
          <p className={styles.note}>
            Only Female/Male cards map to production assets. Extra poses are visual placeholders —
            photographic catalog art is not available in-repo.
          </p>
        </>
      )}
    </aside>
  )
}
