import { useRef, type ReactNode } from 'react'
import { UI_ASSETS } from '@/assets/uiAssets'
import styles from './ModelPanel.module.css'

export type ModelChoice = 'female' | 'male' | 'custom' | 'blank'

type Props = {
  selected: ModelChoice
  customPreviewUrl: string | null
  onSelect: (choice: ModelChoice) => void
  onCustomFile: (file: File) => void
}

export function ModelPanel({ selected, customPreviewUrl, onSelect, onCustomFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <aside className={styles.panel} aria-label="Models">
      <div className={styles.head}>
        <h2>Models</h2>
        <p>Reference figures</p>
      </div>

      <div className={styles.chips} aria-label="Model filter">
        <button
          type="button"
          className={selected === 'female' ? styles.chipActive : styles.chip}
          onClick={() => onSelect('female')}
        >
          Female
        </button>
        <button
          type="button"
          className={selected === 'male' ? styles.chipActive : styles.chip}
          onClick={() => onSelect('male')}
        >
          Male
        </button>
      </div>

      <div className={styles.grid}>
        <ModelCard
          label="Female"
          selected={selected === 'female'}
          onClick={() => onSelect('female')}
        >
          <img src={UI_ASSETS.model.female} alt="" className={styles.croquis} />
        </ModelCard>
        <ModelCard label="Male" selected={selected === 'male'} onClick={() => onSelect('male')}>
          <img src={UI_ASSETS.model.male} alt="" className={styles.croquis} />
        </ModelCard>
        <ModelCard
          label="Custom"
          selected={selected === 'custom'}
          onClick={() => inputRef.current?.click()}
        >
          {customPreviewUrl ? (
            <img src={customPreviewUrl} alt="" className={styles.croquis} />
          ) : (
            <img src={UI_ASSETS.model.custom} alt="" className={styles.croquis} />
          )}
        </ModelCard>
        <ModelCard label="Blank" selected={selected === 'blank'} onClick={() => onSelect('blank')}>
          <img src={UI_ASSETS.model.blank} alt="" className={styles.croquis} />
        </ModelCard>
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

function ModelCard({
  label,
  selected,
  onClick,
  children,
}: {
  label: string
  selected: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={selected ? styles.cardSelected : styles.card}
      onClick={onClick}
      aria-label={`${label} model`}
      aria-pressed={selected}
    >
      <div className={styles.thumb}>{children}</div>
      <span className={styles.label}>{label}</span>
      <span className={selected ? styles.checkOn : styles.checkOff} aria-hidden />
    </button>
  )
}
