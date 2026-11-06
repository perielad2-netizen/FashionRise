import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, BookmarkPlus, MoreHorizontal, Redo2, Sparkles, Star, Undo2 } from 'lucide-react'
import type { SaveStatus } from '@/lib/draftDocument'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './WorkspaceHeader.module.css'

type Props = {
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onClear: () => void
  onMagic: () => void
  magicEnabled?: boolean
  magicBusy?: boolean
  canRecoverLastMagic?: boolean
  onRecoverLastMagic?: () => void
  onComingSoon?: (label: string) => void
  saveStatus: SaveStatus
  saveStatusLabel: string
  saveError: string | null
  onRetrySave?: () => void
  onSaveDesign?: () => void
  onOpenLibrary?: () => void
}

export function WorkspaceHeader({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onClear,
  onMagic,
  magicEnabled = false,
  magicBusy = false,
  canRecoverLastMagic = false,
  onRecoverLastMagic,
  onComingSoon,
  saveStatus,
  saveStatusLabel,
  saveError,
  onRetrySave,
  onSaveDesign,
  onOpenLibrary,
}: Props) {
  const { user } = useAuth()
  const starsUnlimited = Boolean(user?.ai_stars_unlimited)
  const starsBalance = starsUnlimited ? null : Number(user?.ai_stars ?? 0)
  const magicCost = 10
  const canAffordMagic = starsUnlimited || (starsBalance ?? 0) >= magicCost
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
    <div className={`${styles.header} ${menuOpen ? styles.headerMenuOpen : ''}`}>
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
        <span
          className={styles.starsBadge}
          title={
            starsUnlimited
              ? 'Unlimited Stars (owner)'
              : `AI Stars — Magic costs ${magicCost}. New profiles start with ${magicCost}.`
          }
          aria-label={
            starsUnlimited ? 'Unlimited Stars' : `${starsBalance ?? 0} Stars`
          }
        >
          <Star size={14} aria-hidden />
          {starsUnlimited ? '∞' : starsBalance ?? 0}
        </span>
        <button
          type="button"
          className={magicEnabled ? styles.magicReady : styles.magicSoon}
          onClick={onMagic}
          disabled={magicEnabled && (magicBusy || !canAffordMagic)}
          aria-busy={magicEnabled && magicBusy}
          title={
            !magicEnabled
              ? 'Magic is not available in this beta'
              : magicBusy
                ? 'Magic is already running'
                : !canAffordMagic
                  ? `Not enough Stars (need ${magicCost})`
                  : `Turn your sketch into a finished fashion look (−${magicCost} Stars)`
          }
        >
          <Sparkles size={15} />
          Magic
          {magicEnabled && !starsUnlimited ? (
            <span className={styles.soon}>−{magicCost}</span>
          ) : null}
          {magicEnabled ? null : <span className={styles.soon}>Soon</span>}
        </button>
        {onSaveDesign ? (
          <button
            type="button"
            className={styles.saveDesign}
            onClick={onSaveDesign}
            aria-label="Save design"
            title="Save a named private copy to My Designs"
          >
            <BookmarkPlus size={15} aria-hidden="true" />
            <span className={styles.saveDesignLabel}>Save design</span>
          </button>
        ) : null}
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
              {onSaveDesign ? (
                <button
                  type="button"
                  role="menuitem"
                  className={styles.moreItem}
                  onClick={() => {
                    setMenuOpen(false)
                    onSaveDesign()
                  }}
                >
                  Save as design…
                </button>
              ) : null}
              {onOpenLibrary ? (
                <button
                  type="button"
                  role="menuitem"
                  className={styles.moreItem}
                  onClick={() => {
                    setMenuOpen(false)
                    onOpenLibrary()
                  }}
                >
                  My Designs
                </button>
              ) : null}
              {magicEnabled && canRecoverLastMagic && onRecoverLastMagic ? (
                <button
                  type="button"
                  role="menuitem"
                  className={styles.moreItem}
                  disabled={magicBusy}
                  onClick={() => {
                    setMenuOpen(false)
                    onRecoverLastMagic()
                  }}
                >
                  See last result
                </button>
              ) : null}
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
