import { useEffect, useState } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { modelLabel } from '@/assets/modelLibrary'
import { matchStudioShortcut } from '@/lib/studioShortcuts'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { SaveDesignDialog } from '@/components/studio/SaveDesignDialog'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { BrushControls } from '@/shell/components/BrushControls'
import { DrawingWorkspace } from '@/shell/components/DrawingWorkspace'
import { FloatingToolRail } from '@/shell/components/FloatingToolRail'
import { ModelLibraryPanel } from '@/shell/components/ModelLibraryPanel'
import { BetaNotice } from '@/shell/components/BetaNotice'
import { MagicLookPanel } from '@/shell/components/MagicLookPanel'
import { SettingsInspector } from '@/shell/components/SettingsInspector'
import { WorkspaceHeader } from '@/shell/components/WorkspaceHeader'
import type { StudioEditor } from '@/hooks/useStudioEditor'
import styles from './CreatorWorkspace.module.css'

type Dock = 'models' | 'materials' | 'settings' | 'brush' | null

type Props = {
  editor: StudioEditor
  onOpenLibrary?: () => void
}

function modalOpen(): boolean {
  return document.querySelector('[aria-modal="true"]') !== null
}

export function CreatorWorkspace({ editor, onOpenLibrary }: Props) {
  const [dock, setDock] = useState<Dock>(null)
  const [focusMode, setFocusMode] = useState(false)
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

  const { setTool, undo, redo } = editor

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const action = matchStudioShortcut(event)
      if (!action || modalOpen()) return
      event.preventDefault()
      if (action === 'draw') setTool('draw')
      else if (action === 'erase') setTool('erase')
      else if (action === 'fill') setTool('fill')
      else if (action === 'eyedropper') setTool('eyedropper')
      else if (action === 'undo') undo()
      else redo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setTool, undo, redo])

  useEffect(() => {
    if (!dock && !focusMode) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || modalOpen()) return
      if (dock) {
        setDock(null)
        return
      }
      if (focusMode) setFocusMode(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dock, focusMode])

  const toolLabel =
    editor.tool === 'erase'
      ? 'Eraser'
      : editor.tool === 'fill'
        ? 'Fill'
        : editor.tool === 'eyedropper'
          ? 'Eyedropper'
          : 'Pencil'
  const brushOverlay = dock === 'brush' && tablet
  const betaNotice = editor.magicNotice
    ? { message: editor.magicNotice, dismiss: () => editor.setMagicNotice(null) }
    : editor.comingSoon
      ? { message: editor.comingSoon, dismiss: () => editor.setComingSoon(null) }
      : editor.studioNotice
        ? { message: editor.studioNotice, dismiss: () => editor.setStudioNotice(null) }
        : null

  return (
    <section
      className={`${styles.workspace} ${focusMode ? styles.focusMode : ''}`}
      aria-label="Creator workspace"
    >
      <WorkspaceHeader
        canUndo={editor.canUndo}
        canRedo={editor.canRedo}
        onUndo={editor.undo}
        onRedo={editor.redo}
        onClear={editor.clear}
        onMagic={editor.onMagic}
        magicEnabled={editor.magicEnabled}
        magicBusy={editor.magicBusy}
        canRecoverLastMagic={editor.magicCanRecover}
        onRecoverLastMagic={editor.recoverLastMagic}
        onComingSoon={editor.showComingSoon}
        saveStatus={editor.saveStatus}
        saveStatusLabel={editor.saveStatusLabel}
        saveError={editor.saveError}
        onRetrySave={editor.retrySave}
        onSaveDesign={editor.beginSaveDesign}
        onExportPng={() => void editor.exportPng()}
        exporting={editor.exporting}
        onOpenLibrary={onOpenLibrary}
      />

      {betaNotice ? (
        <BetaNotice message={betaNotice.message} onDismiss={betaNotice.dismiss} />
      ) : null}

      <MagicLookPanel
        open={editor.magicOpen}
        phase={editor.magicPhase}
        result={editor.magicResult}
        lookObjectUrl={editor.magicLookUrl}
        sketchObjectUrl={editor.magicSketchUrl}
        error={editor.magicError}
        canRecover={editor.magicCanRecover}
        onClose={editor.closeMagicPanel}
        onCancel={editor.cancelMagicWait}
        onDownload={editor.downloadMagicLook}
        onRecover={editor.recoverLastMagic}
        onBackToSketch={editor.backToSketchFromMagic}
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
        <button
          type="button"
          className={focusMode ? styles.dockActive : styles.dockBtn}
          aria-pressed={focusMode}
          onClick={() => {
            setFocusMode((v) => !v)
            setDock(null)
          }}
        >
          {focusMode ? 'Exit focus' : 'Focus'}
        </button>
      </div>

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
          <div className={styles.canvasStage}>
            <DrawingWorkspace
              strokes={editor.strokes}
              fills={editor.fills}
              tool={editor.tool}
              brushColor={editor.color}
              brushSize={editor.brushSize}
              brushOpacity={editor.opacity}
              fillStyle={editor.fillStyle}
              referenceUrl={editor.referenceUrl}
              referenceOpacity={editor.referenceOpacity}
              onStrokeComplete={editor.onStrokeComplete}
              onFillComplete={editor.onFillComplete}
              onFillError={editor.onFillError}
              onEyedropperSample={editor.onEyedropperSample}
            />
            <button
              type="button"
              className={styles.focusToggle}
              aria-pressed={focusMode}
              aria-label={focusMode ? 'Exit focused sketch mode' : 'Enter focused sketch mode'}
              title={focusMode ? 'Exit focus mode (Esc)' : 'Expand canvas'}
              onClick={() => {
                setFocusMode((v) => !v)
                setDock(null)
              }}
            >
              {focusMode ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              <span>{focusMode ? 'Exit focus' : 'Focus'}</span>
            </button>
            {focusMode ? (
              <div className={styles.focusQuick} aria-label="Focus mode panels">
                <button type="button" onClick={() => setDock('models')}>
                  Models
                </button>
                <button type="button" onClick={() => setDock('materials')}>
                  Materials
                </button>
                <button type="button" onClick={() => setDock('settings')}>
                  Settings
                </button>
              </div>
            ) : null}
          </div>
          <div className={`${styles.materialsSlot} ${dock === 'materials' ? styles.slotOpen : ''}`}>
            <ColorAndMaterialsPanel
              color={editor.color}
              onColor={editor.setColor}
              onColorHex={editor.setColorHex}
              fillStyle={editor.fillStyle}
              onFillStyle={editor.setFillStyle}
              eyedropperActive={editor.tool === 'eyedropper'}
              onToggleEyedropper={() =>
                editor.setTool(editor.tool === 'eyedropper' ? 'draw' : 'eyedropper')
              }
              onNotice={editor.publishStudioNotice}
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
            onSize={editor.setSizeId}
            onBrushSize={editor.setBrushSizePx}
            onOpacity={editor.setBrushOpacity}
            onToggleDim={() => editor.setDimmed((v) => !v)}
            onMagic={editor.onMagic}
          />
        </div>
      </div>

      {brushOverlay ? (
        <div className={styles.brushOverlay}>
          <button
            type="button"
            className={styles.brushScrim}
            aria-label="Close brush panel"
            onClick={() => setDock(null)}
          />
          <div className={styles.brushSheet} role="dialog" aria-label="Brush settings sheet">
            <div className={styles.brushSheetHead}>
              <strong>Brush</strong>
              <button type="button" className={styles.brushClose} onClick={() => setDock(null)}>
                Done
              </button>
            </div>
            <BrushControls
              tool={editor.tool}
              brushSize={editor.brushSize}
              opacity={editor.opacity}
              onBrushSize={editor.setBrushSizePx}
              onOpacity={editor.setBrushOpacity}
            />
          </div>
        </div>
      ) : null}

      {editor.modelSwitchPrompt ? (
        <ConfirmDialog
          title="Change reference model?"
          actions={[
            { label: 'Cancel', onClick: editor.cancelModelSwitch, variant: 'ghost' },
            {
              label: 'Keep strokes',
              onClick: () => editor.confirmModelKeepStrokes(),
              variant: 'primary',
            },
            {
              label: 'Clear strokes',
              onClick: () => editor.confirmModelClearStrokes(),
              variant: 'danger',
            },
          ]}
        >
          <p>
            Your current sketch will stay on the canvas if you keep strokes. Clearing removes ink
            before switching to{' '}
            <strong>{modelLabel(editor.modelSwitchPrompt.next)}</strong>.
          </p>
        </ConfirmDialog>
      ) : null}

      {editor.draftConflict ? (
        <ConfirmDialog
          title="Draft recovery conflict"
          actions={[
            {
              label: 'Use cloud draft',
              onClick: editor.resolveConflictUseServer,
              variant: 'ghost',
            },
            {
              label: 'Keep this device',
              onClick: editor.resolveConflictKeepLocal,
              variant: 'primary',
            },
          ]}
        >
          <p>
            This device and your private cloud draft both have changes. Both copies are kept until
            you choose. Nothing is overwritten automatically.
          </p>
        </ConfirmDialog>
      ) : null}

      {editor.saveDesignDialog && !editor.draftConflict && !editor.modelSwitchPrompt ? (
        <SaveDesignDialog
          defaultTitle={editor.saveDesignDialog.defaultTitle}
          saving={editor.saveDesignDialog.saving}
          error={editor.saveDesignDialog.error}
          customReferenceOmitted={editor.saveDesignDialog.customReferenceOmitted}
          onConfirm={(title) => void editor.confirmSaveDesign(title)}
          onCancel={editor.cancelSaveDesign}
        />
      ) : null}
    </section>
  )
}
