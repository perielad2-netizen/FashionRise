import { useState } from 'react'
import { ColorAndMaterialsPanel } from '@/design-lab/components/ColorAndMaterialsPanel'
import { DrawingWorkspace } from '@/design-lab/components/DrawingWorkspace'
import { FloatingToolRail } from '@/design-lab/components/FloatingToolRail'
import { ModelLibraryPanel } from '@/design-lab/components/ModelLibraryPanel'
import { SettingsInspector } from '@/design-lab/components/SettingsInspector'
import { WorkspaceHeader } from '@/design-lab/components/WorkspaceHeader'
import styles from './CreatorWorkspace.module.css'

type Dock = 'models' | 'materials' | 'settings' | null

export function CreatorWorkspace() {
  const [dock, setDock] = useState<Dock>(null)

  return (
    <section className={styles.workspace} aria-label="Creator workspace prototype">
      <WorkspaceHeader />
      <div className={styles.mobileDock} aria-label="Prototype panel docks">
        <button
          type="button"
          className={dock === 'models' ? styles.dockActive : styles.dockBtn}
          onClick={() => setDock(dock === 'models' ? null : 'models')}
        >
          Models
        </button>
        <button
          type="button"
          className={dock === 'materials' ? styles.dockActive : styles.dockBtn}
          onClick={() => setDock(dock === 'materials' ? null : 'materials')}
        >
          Materials
        </button>
        <button
          type="button"
          className={dock === 'settings' ? styles.dockActive : styles.dockBtn}
          onClick={() => setDock(dock === 'settings' ? null : 'settings')}
        >
          Settings
        </button>
      </div>
      <div className={styles.body}>
        <div
          className={`${styles.modelsSlot} ${dock === 'models' ? styles.slotOpen : ''}`}
          data-dock="models"
        >
          <ModelLibraryPanel />
        </div>
        <div className={styles.center}>
          <FloatingToolRail />
          <DrawingWorkspace />
          <div
            className={`${styles.materialsSlot} ${dock === 'materials' ? styles.slotOpen : ''}`}
            data-dock="materials"
          >
            <ColorAndMaterialsPanel />
          </div>
        </div>
        <div
          className={`${styles.settingsSlot} ${dock === 'settings' ? styles.slotOpen : ''}`}
          data-dock="settings"
        >
          <SettingsInspector />
        </div>
      </div>
    </section>
  )
}
