import { ArrowLeft, Check, MoreHorizontal, Redo2, Sparkles, Undo2 } from 'lucide-react'
import styles from './WorkspaceHeader.module.css'

export function WorkspaceHeader() {
  return (
    <div className={styles.header}>
      <div className={styles.left}>
        <button type="button" className={styles.iconBtn} tabIndex={-1} aria-label="Back" aria-disabled>
          <ArrowLeft size={18} />
        </button>
        <h1 className={styles.title}>New Design</h1>
      </div>
      <div className={styles.right}>
        <span className={styles.autosave}>
          <Check size={14} />
          Auto Save
        </span>
        <button type="button" className={styles.iconBtn} tabIndex={-1} aria-label="Undo" aria-disabled>
          <Undo2 size={17} />
        </button>
        <button type="button" className={styles.iconBtn} tabIndex={-1} aria-label="Redo" aria-disabled>
          <Redo2 size={17} />
        </button>
        <button type="button" className={styles.magic} tabIndex={-1} aria-disabled>
          <Sparkles size={15} />
          Magic
        </button>
        <button type="button" className={styles.iconBtn} tabIndex={-1} aria-label="More" aria-disabled>
          <MoreHorizontal size={18} />
        </button>
      </div>
    </div>
  )
}
