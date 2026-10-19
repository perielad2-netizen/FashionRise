import { useEffect, useState } from 'react'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { DrawingWorkspace } from '@/shell/components/DrawingWorkspace'
import { FloatingBrushPanel } from '@/shell/components/FloatingBrushPanel'
import { FloatingToolRail } from '@/shell/components/FloatingToolRail'
import { ModelLibraryPanel } from '@/shell/components/ModelLibraryPanel'
import { SettingsInspector } from '@/shell/components/SettingsInspector'
import { WorkspaceHeader } from '@/shell/components/WorkspaceHeader'
import type { StudioEditor } from '@/hooks/useStudioEditor'
import styles from './CreatorWorkspace.module.css'

type Dock = 'models' | 'materials' | 'settings' | 'brush' | null

type Props = {
  editor: StudioEditor
}

export function CreatorWorkspace({ editor }: Props) {
  const [dock, setDock] = useState<Dock>(null)
  const [narrow, setNarrow] = useState(false)
  const [tablet, setTablet] = useState(false)

  useEffect(() => {
    const n = window.matchMedia('(max-width: 820px)')
    const t = window.matchMedia('(max-width: 1024px)')
    const apply = () => {
      setNarrow(n.matches)
      setTablet(t.matches)
    }
    apply()
    n.addEventListener('change', apply)
    t.addEventListener('change', apply)
    return () => {
      n.removeEventListener('change', apply)
      t.removeEventListener('change', apply)
    }
  }, [])

  const toolLabel = editor.tool === 'erase' ? 'Eraser' : 'Pencil'
  const showFloatingBrush = !narrow

  return (
    <section className={styles.workspace} aria-label="Creator workspace">
      <WorkspaceHeader
        canUndo={editor.canUndo}
        canRedo={editor.canRedo}
        onUndo={editor.undo}
        onRedo={editor.redo}
        onClear={editor.clear}
        onMagic={editor.onMagic}
        onComingSoon={editor.showComingSoon}
      />

      <div className={styles.mobileDock} aria-label="Studio panels">
        <button
          type="button"
          className={dock === 'models' ? styles.dockActive : styles.dockBtn}
          onClick={() => setDock(dock === 'models' ? null : 'models')}
        >
          Models
        </button>
        <button
          type="button"
          className={dock === 'brush' ? styles.dockActive : styles.dockBtn}
          onClick={() => setDock(dock === 'brush' ? null : 'brush')}
        >
          Brush panel
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

      {dock === 'brush' && (narrow || tablet) ? (
        <div className={styles.brushSheet} role="dialog" aria-label="Brush settings sheet">
          <FloatingBrushPanel
            tool={editor.tool}
            brushSize={editor.brushSize}
            opacity={editor.opacity}
            onBrushSize={editor.setBrushSizePx}
            onOpacity={editor.setBrushOpacity}
            hiddenOnNarrow={false}
            variant="sheet"
          />
        </div>
      ) : null}

      <div className={styles.body}>
        <div className={`${styles.modelsSlot} ${dock === 'models' ? styles.slotOpen : ''}`}>
          <ModelLibraryPanel
            selected={editor.model}
            customPreviewUrl={editor.customUrl}
            onSelect={editor.setModel}
            onCustomFile={editor.onCustomFile}
          />
        </div>

        <div className={styles.center}>
          <FloatingToolRail
            tool={editor.tool}
            canUndo={editor.canUndo}
            canRedo={editor.canRedo}
            onTool={editor.setTool}
            onUndo={editor.undo}
            onRedo={editor.redo}
            orientation={narrow ? 'horizontal' : 'vertical'}
          />
          <DrawingWorkspace
            strokes={editor.strokes}
            tool={editor.tool}
            brushColor={editor.color}
            brushSize={editor.brushSize}
            brushOpacity={editor.opacity}
            referenceUrl={editor.referenceUrl}
            referenceOpacity={editor.referenceOpacity}
            onStrokeComplete={editor.onStrokeComplete}
            onBrushSize={editor.setBrushSizePx}
            onOpacity={editor.setBrushOpacity}
            showFloatingBrush={showFloatingBrush}
          />
          <div className={`${styles.materialsSlot} ${dock === 'materials' ? styles.slotOpen : ''}`}>
            <ColorAndMaterialsPanel
              color={editor.color}
              onColor={editor.setColor}
              onColorHex={editor.setColorHex}
            />
          </div>
        </div>

        <div className={`${styles.settingsSlot} ${dock === 'settings' ? styles.slotOpen : ''}`}>
          <SettingsInspector
            sizeId={editor.sizeId}
            brushSize={editor.brushSize}
            opacity={editor.opacity}
            dimmed={editor.dimmed}
            toolLabel={toolLabel}
            magicNotice={editor.magicNotice}
            studioNotice={editor.studioNotice}
            comingSoon={editor.comingSoon}
            onSize={editor.setSizeId}
            onBrushSize={editor.setBrushSizePx}
            onOpacity={editor.setBrushOpacity}
            onToggleDim={() => editor.setDimmed((v) => !v)}
            onMagic={editor.onMagic}
            onDismissMagic={() => editor.setMagicNotice(null)}
            onDismissStudioNotice={() => editor.setStudioNotice(null)}
            onDismissComingSoon={() => editor.setComingSoon(null)}
          />
        </div>
      </div>
    </section>
  )
}
