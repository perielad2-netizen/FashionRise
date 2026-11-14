import { useEffect, useRef, useState } from 'react'
import {
  BookmarkPlus,
  MoreHorizontal,
  Redo2,
  Sparkles,
  Star,
  Undo2,
} from 'lucide-react'
import type { SaveStatus } from '@/lib/draftDocument'
import { useAuth } from '@/services/auth/AuthProvider'
import { AiSpendConfirmDialog } from '@/shell/components/AiSpendConfirmDialog'
import { StarsShopModal } from '@/shell/components/StarsShopModal'
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
  saveStatus: SaveStatus
  saveStatusLabel: string
  saveError: string | null
  onRetrySave?: () => void
  onSaveDesign?: () => void
  onOpenLibrary?: () => void
  onOpenSettings?: () => void
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
  saveStatus,
  saveStatusLabel,
  saveError,
  onRetrySave,
  onSaveDesign,
  onOpenLibrary: _onOpenLibrary,
  onOpenSettings,
}: Props) {
  void _onOpenLibrary
  const { user } = useAuth()
  const starsUnlimited = Boolean(user?.ai_stars_unlimited)
  const starsBalance = starsUnlimited ? null : Number(user?.ai_stars ?? 0)
  const magicCost = 10
  const [menuOpen, setMenuOpen] = useState(false)
  const [shopOpen, setShopOpen] = useState(false)
  const [magicSpendOpen, setMagicSpendOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    // V2-0001: pointerdown covers touch/WebView outside taps (mousedown alone is flaky).
    const onDoc = (e: Event) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('pointerdown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  useEffect(() => {
    if (!magicBusy) return
    setMenuOpen(false)
    setMagicSpendOpen(false)
  }, [magicBusy])

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
      <div className={styles.brand}>
        <h1 className={styles.title}>New Design</h1>
      </div>

      <div className={styles.meta}>
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
          className={`${styles.iconBtn} ${styles.headerHistory}`}
          aria-label="Undo"
          disabled={!canUndo}
          onClick={onUndo}
        >
          <Undo2 size={17} />
        </button>
        <button
          type="button"
          className={`${styles.iconBtn} ${styles.headerHistory}`}
          aria-label="Redo"
          disabled={!canRedo}
          onClick={onRedo}
        >
          <Redo2 size={17} />
        </button>
        <button
          type="button"
          className={styles.starsBadge}
          onClick={() => setShopOpen(true)}
          title={
            starsUnlimited
              ? 'Unlimited Stars — open shop'
              : `AI Stars — Magic 10 · Model 10 · Fabric 5 · PDF 50. Tap for packages.`
          }
          aria-label={
            starsUnlimited ? 'Unlimited Stars, open shop' : `${starsBalance ?? 0} Stars, open shop`
          }
        >
          <Star size={14} aria-hidden />
          {starsUnlimited ? '∞' : starsBalance ?? 0}
        </button>
      </div>

      <div className={styles.ctaRow}>
        <button
          type="button"
          className={magicEnabled ? styles.magicReady : styles.magicSoon}
          onClick={() => {
            if (!magicEnabled) {
              onMagic()
              return
            }
            setMagicSpendOpen(true)
          }}
          disabled={magicEnabled && magicBusy}
          aria-busy={magicEnabled && magicBusy}
          title={
            !magicEnabled
              ? 'Magic is not available in this beta'
              : magicBusy
                ? 'Magic is already running'
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
      </div>

      {/* Hide More while Magic is creating — z-index sat above the Magic overlay. */}
      {!magicBusy ? (
      <div className={styles.moreWrap} ref={menuRef} data-testid="workspace-more">
        <button
          type="button"
          className={styles.moreBtn}
          aria-label="More"
          aria-expanded={menuOpen}
          title="More — Settings, Clear canvas"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <MoreHorizontal size={18} aria-hidden />
          <span className={styles.moreBtnLabel}>More</span>
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
            {onOpenSettings ? (
              <button
                type="button"
                role="menuitem"
                className={styles.moreItem}
                onClick={() => {
                  setMenuOpen(false)
                  onOpenSettings()
                }}
              >
                Settings
              </button>
            ) : null}
            {magicEnabled && canRecoverLastMagic && onRecoverLastMagic ? (
              <button
                type="button"
                role="menuitem"
                className={styles.moreItem}
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
          </div>
        ) : null}
      </div>
      ) : null}

      <AiSpendConfirmDialog
        open={magicSpendOpen}
        feature="magic"
        cost={magicCost}
        balance={starsBalance}
        unlimited={starsUnlimited}
        busy={magicBusy}
        description="Fashion Magic and Try On Person use Stars from your wallet."
        onCancel={() => setMagicSpendOpen(false)}
        onApproved={() => {
          setMagicSpendOpen(false)
          onMagic()
        }}
        onOpenShop={() => setShopOpen(true)}
      />
      <StarsShopModal open={shopOpen} onClose={() => setShopOpen(false)} />
    </div>
  )
}
