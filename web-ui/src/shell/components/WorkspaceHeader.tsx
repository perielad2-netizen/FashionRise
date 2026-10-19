import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, MoreHorizontal, Redo2, Sparkles, Undo2 } from 'lucide-react'
import styles from './WorkspaceHeader.module.css'

type Props = {
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onClear: () => void
  onMagic: () => void
  onComingSoon?: (label: string) => void
}

export function WorkspaceHeader({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onClear,
  onMagic,
  onComingSoon,
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

  return (
    <div className={styles.header}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Back"
          onClick={() => onComingSoon?.('Home')}
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className={styles.title}>New Design</h1>
      </div>
      <div className={styles.right}>
        <span className={styles.sessionStatus} title="Drawings stay in this browser tab until save is available">
          Unsaved session
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
        <button type="button" className={styles.magic} onClick={onMagic}>
          <Sparkles size={15} />
          Magic
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
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
