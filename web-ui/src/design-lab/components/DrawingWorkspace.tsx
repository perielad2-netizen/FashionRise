import { Maximize2, ScanSearch, Search } from 'lucide-react'
import { DESIGN_LAB_CANVAS_CROQUIS } from '@/design-lab/designLabAssets'
import { FloatingBrushPanel } from '@/design-lab/components/FloatingBrushPanel'
import styles from './DrawingWorkspace.module.css'

export function DrawingWorkspace() {
  return (
    <div className={styles.wrap}>
      <div className={styles.canvasFrame}>
        <img
          src={DESIGN_LAB_CANVAS_CROQUIS}
          alt="Fashion croquis reference"
          className={styles.croquis}
          draggable={false}
        />
        <div
          className={styles.sketchHint}
          aria-hidden
          title="Finished sketch artwork from mockup is not available as a licensed asset"
        />
        <div className={styles.zoom} aria-label="Zoom controls prototype">
          <button type="button" className={styles.zoomBtn} tabIndex={-1} aria-disabled>
            <Search size={14} />
          </button>
          <span>100%</span>
          <button type="button" className={styles.zoomBtn} tabIndex={-1} aria-disabled>
            <ScanSearch size={14} />
          </button>
          <button type="button" className={styles.zoomBtn} tabIndex={-1} aria-disabled>
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
      <FloatingBrushPanel />
    </div>
  )
}
