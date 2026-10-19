import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, MoreHorizontal, Redo2, Sparkles, Undo2 } from 'lucide-react'
import type { SaveStatus } from '@/lib/draftDocument'
import styles from './WorkspaceHeader.module.css'

type Props = {
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onClear: () => void
  onMagic: () => void
  onComingSoon?: (label: string) => void
  saveStatus: SaveStatus
  saveStatusLabel: string
  saveError: string | null
  onRetrySave?: () => void
}

export function WorkspaceHeader({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onClear,
  onMagic,
  onComingSoon,
  saveStatus,
  saveStatusLabel,
  saveError,
  onRetrySave,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuOpen])

  const statusClass =
    saveStatus === 'error'
      ? styles.statusError
      : saveStatus === 'saving' || saveStatus === 'restoring'
        ? styles.statusBusy
        : saveStatus === 'saved' || saveStatus === 'local-only'
          ? styles.statusSaved
          : styles.sessionStatus

  return (
    <div className={styles.header}>
      <div className={styles.left}>
        <button
          type="button"
          className={`${styles.iconBtn} ${styles.unavailable}`}
          aria-label="Home, coming later"
          title="Home is coming later"
          onClick={() => onComingSoon?.('Home')}
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className={styles.title}>New Design</h1>
      </div>
      <div className={styles.right}>
        <span
          className={statusClass}
          title={saveError ?? 'Private draft for your account'}
          role="status"
          aria-live="polite"
        >
          {saveStatusLabel}
          {saveStatus === 'error' && onRetrySave ? (
            <button type="button" className={styles.retry} onClick={onRetrySave}>
              Retry
            </button>
          ) : null}
        </span>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Undo"
          disabled={!canUndo}
          onClick={onUndo}
        >
          <Undo2 size={17} />
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Redo"
          disabled={!canRedo}
          onClick={onRedo}
        >
          <Redo2 size={17} />
        </button>
        <button
          type="button"
          className={styles.magicSoon}
          onClick={onMagic}
          title="Magic is not available in this beta"
        >
          <Sparkles size={15} />
          Magic
          <span className={styles.soon}>Soon</span>
        </button>
        <div className={styles.moreWrap} ref={menuRef}>
          <button
            type="button"
            className={styles.iconBtn}
            aria-label="More"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <MoreHorizontal size={18} />
          </button>
          {menuOpen ? (
            <div className={styles.moreMenu} role="menu">
              <button
                type="button"
                role="menuitem"
                className={styles.moreItem}
                onClick={() => {
                  setMenuOpen(false)
                  onClear()
                }}
              >
                Clear canvas
              </button>
              {onRetrySave ? (
                <button
                  type="button"
                  role="menuitem"
                  className={styles.moreItem}
                  onClick={() => {
                    setMenuOpen(false)
                    onRetrySave()
                  }}
                >
                  Save now
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
