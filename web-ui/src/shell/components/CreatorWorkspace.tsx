import { useCallback, useEffect, useRef, useState } from 'react'
import { Expand, Maximize2, Minimize2 } from 'lucide-react'
import { modelLabel } from '@/assets/modelLibrary'
import { matchStudioShortcut } from '@/lib/studioShortcuts'
import {
  centerPan,
  fitPage,
  fitWidth,
  hundredPercent,
  type ViewportState,
  zoomAt,
  zoomPercent,
} from '@/lib/viewportTransform'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import { SaveDesignDialog } from '@/components/studio/SaveDesignDialog'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { BrushControls } from '@/shell/components/BrushControls'
import { DrawingWorkspace } from '@/shell/components/DrawingWorkspace'
import { FloatingToolRail } from '@/shell/components/FloatingToolRail'
import { ImmersiveToolbar, type ImmersiveTool } from '@/shell/components/ImmersiveToolbar'
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

function fullscreenElement(): Element | null {
  const doc = document as Document & { webkitFullscreenElement?: Element | null }
  return document.fullscreenElement ?? doc.webkitFullscreenElement ?? null
}

export function CreatorWorkspace({ editor, onOpenLibrary }: Props) {
  const [dock, setDock] = useState<Dock>(null)
  const [focusMode, setFocusMode] = useState(false)
  const [immersive, setImmersive] = useState(false)
  const [nativeFullscreen, setNativeFullscreen] = useState(false)
  const [panTool, setPanTool] = useState(false)
  const [viewport, setViewport] = useState<ViewportState>(() =>
    fitPage({ width: 800, height: 1000 }),
  )
  const [narrow, setNarrow] = useState(false)
  const [tablet, setTablet] = useState(false)
  const workspaceRef = useRef<HTMLElement | null>(null)
  const immersiveTool: ImmersiveTool = panTool ? 'pan' : editor.tool
  const preImmersiveTool = useRef(editor.tool)

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

  const exitNativeFullscreen = useCallback(async () => {
    const doc = document as Document & {
      webkitExitFullscreen?: () => Promise<void> | void
    }
    if (!fullscreenElement()) return
    try {
      if (document.exitFullscreen) await document.exitFullscreen()
      else if (doc.webkitExitFullscreen) await doc.webkitExitFullscreen()
    } catch {
      /* browser may reject; immersive CSS fallback still exits */
    }
  }, [])

  const exitImmersive = useCallback(() => {
    // Clear immersive UI immediately; fullscreen exit may reject or lag on some browsers.
    setImmersive(false)
    setNativeFullscreen(false)
    setPanTool(false)
    setDock(null)
    // Restore last drawing tool if Hand was active (editor.tool is unchanged while panning).
    setTool(preImmersiveTool.current)
    void exitNativeFullscreen()
  }, [exitNativeFullscreen, setTool])

  const enterImmersive = useCallback(async () => {
    preImmersiveTool.current = editor.tool
    setDock(null)
    setPanTool(false)
    setImmersive(true)
    setViewport(fitPage({ width: window.innerWidth, height: window.innerHeight }))
    const el = workspaceRef.current
    if (!el) return
    const req =
      el.requestFullscreen?.bind(el) ??
      (el as HTMLElement & { webkitRequestFullscreen?: () => Promise<void> }).webkitRequestFullscreen?.bind(
        el,
      )
    if (!req) return
    try {
      await req()
      setNativeFullscreen(true)
    } catch {
      setNativeFullscreen(false)
    }
  }, [editor.tool])

  useEffect(() => {
    const onFs = () => {
      const active = !!fullscreenElement()
      setNativeFullscreen(active)
      // Browser exited fullscreen independently — keep immersive CSS fallback until user exits.
    }
    document.addEventListener('fullscreenchange', onFs)
    document.addEventListener('webkitfullscreenchange', onFs as EventListener)
    return () => {
      document.removeEventListener('fullscreenchange', onFs)
      document.removeEventListener('webkitfullscreenchange', onFs as EventListener)
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const action = matchStudioShortcut(event)
      if (!action || modalOpen()) return
      if (immersive && panTool) return
      event.preventDefault()
      if (action === 'draw') {
        setPanTool(false)
        setTool('draw')
      } else if (action === 'erase') {
        setPanTool(false)
        setTool('erase')
      } else if (action === 'fill') {
        setPanTool(false)
        setTool('fill')
      } else if (action === 'eyedropper') {
        setPanTool(false)
        setTool('eyedropper')
      } else if (action === 'undo') undo()
      else redo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [immersive, panTool, redo, setTool, undo])

  useEffect(() => {
    if (!dock && !focusMode && !immersive) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      // 1) Topmost modal / color picker
      if (modalOpen()) return
      // 2) Open dock / sheet
      if (dock) {
        setDock(null)
        return
      }
      // 3) Exit immersive / native fullscreen
      if (immersive) {
        event.preventDefault()
        exitImmersive()
        return
      }
      // 4) Exit Focus
      if (focusMode) setFocusMode(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dock, exitImmersive, focusMode, immersive])

  const toolLabel =
    editor.tool === 'erase'
      ? 'Eraser'
      : editor.tool === 'fill'
        ? 'Fill'
        : editor.tool === 'eyedropper'
          ? 'Eyedropper'
          : 'Pencil'
  const brushOverlay = dock === 'brush' && (tablet || immersive)
  const panelScrim =
    (dock === 'materials' || dock === 'settings' || dock === 'models') &&
    (tablet || narrow || focusMode || immersive)
  const betaNotice = editor.magicNotice
    ? { message: editor.magicNotice, dismiss: () => editor.setMagicNotice(null) }
    : editor.comingSoon
      ? { message: editor.comingSoon, dismiss: () => editor.setComingSoon(null) }
      : editor.studioNotice
        ? { message: editor.studioNotice, dismiss: () => editor.setStudioNotice(null) }
        : null

  const applyImmersiveTool = (next: ImmersiveTool) => {
    if (next === 'pan') {
      setPanTool(true)
      return
    }
    setPanTool(false)
    setTool(next)
  }

  const zoomStep = (dir: 1 | -1) => {
    const host = workspaceRef.current?.querySelector('[data-testid="drawing-canvas-host"]')
    const rect = host?.getBoundingClientRect()
    const box = {
      width: rect?.width || window.innerWidth,
      height: rect?.height || window.innerHeight,
    }
    const factor = dir > 0 ? 1.12 : 1 / 1.12
    setViewport(
      zoomAt(viewport, box, viewport.scale * factor, box.width / 2, box.height / 2),
    )
  }

  return (
    <section
      ref={workspaceRef}
      className={`${styles.workspace} ${focusMode ? styles.focusMode : ''} ${immersive ? styles.immersiveMode : ''}`}
      aria-label="Creator workspace"
      data-immersive={immersive ? 'true' : 'false'}
      data-native-fullscreen={nativeFullscreen ? 'true' : 'false'}
    >
      {!immersive ? (
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
      ) : null}

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

      <div
        className={`${styles.mobileDock} ${tablet && !immersive ? styles.mobileDockVisible : ''}`}
        aria-label="Studio panels"
      >
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
        <button
          type="button"
          className={styles.dockBtn}
          onClick={() => {
            void enterImmersive()
          }}
        >
          Full screen
        </button>
      </div>

      {panelScrim ? (
        <button
          type="button"
          className={styles.panelScrim}
          aria-label="Close panel"
          onClick={() => setDock(null)}
        />
      ) : null}

      <div className={styles.body}>
        <div className={`${styles.modelsSlot} ${dock === 'models' ? styles.slotOpen : ''}`}>
          {(narrow || focusMode || immersive) && dock === 'models' ? (
            <>
              <div className={styles.sheetHead}>
                <strong>Models</strong>
                <button type="button" className={styles.sheetClose} onClick={() => setDock(null)}>
                  Done
                </button>
              </div>
              <div className={styles.sheetBody}>
                <ModelLibraryPanel
                  selected={editor.model}
                  customPreviewUrl={editor.customUrl}
                  onSelect={editor.setModel}
                  onCustomFile={editor.onCustomFile}
                />
              </div>
            </>
          ) : (
            <ModelLibraryPanel
              selected={editor.model}
              customPreviewUrl={editor.customUrl}
              onSelect={editor.setModel}
              onCustomFile={editor.onCustomFile}
            />
          )}
        </div>

        <div className={styles.center}>
          {!immersive ? (
            <FloatingToolRail
              tool={editor.tool}
              canUndo={editor.canUndo}
              canRedo={editor.canRedo}
              onTool={editor.setTool}
              onUndo={editor.undo}
              onRedo={editor.redo}
              orientation={narrow ? 'horizontal' : 'vertical'}
            />
          ) : null}
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
              onBrushSize={editor.setBrushSizePx}
              immersive={immersive}
              panTool={panTool}
              viewport={immersive ? viewport : undefined}
              onViewportChange={immersive ? setViewport : undefined}
            />
            {!immersive ? (
              <div className={styles.canvasActions}>
                <button
                  type="button"
                  className={styles.focusToggle}
                  aria-pressed={focusMode}
                  aria-label={focusMode ? 'Exit focused sketch mode' : 'Enter focused sketch mode'}
                  title={
                    focusMode
                      ? 'Exit focus mode (Esc) — fewer panels, standard paper fit'
                      : 'Focus — fewer panels, standard paper fit'
                  }
                  onClick={() => {
                    setFocusMode((v) => !v)
                    setDock(null)
                  }}
                >
                  {focusMode ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                  <span>{focusMode ? 'Exit focus' : 'Focus'}</span>
                </button>
                <button
                  type="button"
                  className={styles.immersiveToggle}
                  aria-label="Enter full screen drawing"
                  title="Full screen drawing — nearly the whole device, with zoom and pan"
                  onClick={() => void enterImmersive()}
                >
                  <Expand size={16} />
                  <span>Full screen</span>
                </button>
              </div>
            ) : null}
            {focusMode && !tablet && !immersive ? (
              <div className={styles.focusQuick} aria-label="Focus mode panels">
                <button
                  type="button"
                  aria-pressed={dock === 'models'}
                  onClick={() => setDock(dock === 'models' ? null : 'models')}
                >
                  Models
                </button>
                <button
                  type="button"
                  aria-pressed={dock === 'materials'}
                  onClick={() => setDock(dock === 'materials' ? null : 'materials')}
                >
                  Materials
                </button>
                <button
                  type="button"
                  aria-pressed={dock === 'settings'}
                  onClick={() => setDock(dock === 'settings' ? null : 'settings')}
                >
                  Settings
                </button>
              </div>
            ) : null}
            {immersive ? (
              <ImmersiveToolbar
                tool={immersiveTool}
                canUndo={editor.canUndo}
                canRedo={editor.canRedo}
                brushSize={editor.brushSize}
                zoomPercent={zoomPercent(viewport.scale)}
                nativeFullscreen={nativeFullscreen}
                onTool={applyImmersiveTool}
                onUndo={editor.undo}
                onRedo={editor.redo}
                onZoomIn={() => zoomStep(1)}
                onZoomOut={() => zoomStep(-1)}
                onFitPage={() =>
                  setViewport(
                    fitPage({
                      width: workspaceRef.current?.clientWidth || window.innerWidth,
                      height: workspaceRef.current?.clientHeight || window.innerHeight,
                    }),
                  )
                }
                onFitWidth={() =>
                  setViewport(
                    fitWidth({
                      width: workspaceRef.current?.clientWidth || window.innerWidth,
                      height: workspaceRef.current?.clientHeight || window.innerHeight,
                    }),
                  )
                }
                onHundred={() =>
                  setViewport(
                    hundredPercent({
                      width: workspaceRef.current?.clientWidth || window.innerWidth,
                      height: workspaceRef.current?.clientHeight || window.innerHeight,
                    }),
                  )
                }
                onCenter={() =>
                  setViewport(
                    centerPan(viewport.scale, {
                      width: workspaceRef.current?.clientWidth || window.innerWidth,
                      height: workspaceRef.current?.clientHeight || window.innerHeight,
                    }),
                  )
                }
                onOpenMaterials={() => setDock(dock === 'materials' ? null : 'materials')}
                onOpenBrush={() => setDock(dock === 'brush' ? null : 'brush')}
                onOpenModels={() => setDock(dock === 'models' ? null : 'models')}
                onSave={editor.beginSaveDesign}
                onExport={() => void editor.exportPng()}
                onExit={exitImmersive}
                saveLabel={editor.saveStatusLabel || 'Save'}
              />
            ) : null}
          </div>
          <div className={`${styles.materialsSlot} ${dock === 'materials' ? styles.slotOpen : ''}`}>
            {(tablet || narrow || focusMode || immersive) && dock === 'materials' ? (
              <>
                <div className={styles.sheetHead}>
                  <strong>Materials</strong>
                  <button type="button" className={styles.sheetClose} onClick={() => setDock(null)}>
                    Done
                  </button>
                </div>
                <div className={styles.sheetBody}>
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
              </>
            ) : (
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
            )}
          </div>
        </div>

        <div className={`${styles.settingsSlot} ${dock === 'settings' ? styles.slotOpen : ''}`}>
          {(tablet || narrow || focusMode || immersive) && dock === 'settings' ? (
            <>
              <div className={styles.sheetHead}>
                <strong>Settings</strong>
                <button type="button" className={styles.sheetClose} onClick={() => setDock(null)}>
                  Done
                </button>
              </div>
              <div className={styles.sheetBody}>
                <SettingsInspector
                  tool={editor.tool}
                  brushSize={editor.brushSize}
                  opacity={editor.opacity}
                  dimmed={editor.dimmed}
                  toolLabel={toolLabel}
                  onBrushSize={editor.setBrushSizePx}
                  onOpacity={editor.setBrushOpacity}
                  onToggleDim={() => editor.setDimmed((v) => !v)}
                  onMagic={editor.onMagic}
                />
              </div>
            </>
          ) : (
            <SettingsInspector
              tool={editor.tool}
              brushSize={editor.brushSize}
              opacity={editor.opacity}
              dimmed={editor.dimmed}
              toolLabel={toolLabel}
              onBrushSize={editor.setBrushSizePx}
              onOpacity={editor.setBrushOpacity}
              onToggleDim={() => editor.setDimmed((v) => !v)}
              onMagic={editor.onMagic}
            />
          )}
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
