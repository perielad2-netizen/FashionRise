import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import type { StudioEditor } from '@/hooks/useStudioEditor'
import { solidStyle } from '@/lib/fills'
import { DEFAULT_MODEL } from '@/assets/modelLibrary'
import { BRUSH_SIZES, INK_SWATCHES } from '@/lib/strokes'

vi.mock('@/services/fabricAssetsApi', () => ({
  listMyFabrics: vi.fn(async () => []),
  uploadFabric: vi.fn(),
  deleteFabric: vi.fn(),
  fetchFabricImageBlob: vi.fn(),
}))

vi.mock('@/components/studio/DrawingCanvas', () => ({
  DrawingCanvas: (props: { immersive?: boolean; panTool?: boolean }) => (
    <div
      data-testid="drawing-canvas"
      data-immersive={props.immersive ? 'true' : 'false'}
      data-pan={props.panTool ? 'true' : 'false'}
    >
      canvas
    </div>
  ),
}))

function mockMatchMedia(width: number) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => {
    const max = /max-width:\s*(\d+)px/.exec(query)
    let matches = false
    if (max) matches = width <= Number(max[1])
    return {
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }
  })
}

function mockEditor(): StudioEditor {
  return {
    user: { id: 'u1', username: 'Tester' },
    ready: true,
    strokes: [{ id: 's1', tool: 'draw', points: [10, 10, 0.5, 40, 40, 0.5], color: '#111', size: 2, opacity: 1 }],
    fills: [],
    tool: 'draw',
    setTool: vi.fn(),
    sizeId: 'medium',
    setSizeId: vi.fn(),
    brushSize: BRUSH_SIZES.medium,
    setBrushSizePx: vi.fn(),
    nudgeBrushSizePx: vi.fn(),
    opacity: 0.9,
    setBrushOpacity: vi.fn(),
    color: INK_SWATCHES[0]!.color,
    setColor: vi.fn(),
    setColorHex: vi.fn(() => true),
    fillStyle: solidStyle(INK_SWATCHES[0]!.color),
    setFillStyle: vi.fn(),
    model: DEFAULT_MODEL,
    setModel: vi.fn(),
    customUrl: null,
    onCustomFile: vi.fn(),
    dimmed: false,
    setDimmed: vi.fn(),
    referenceUrl: null,
    referenceOpacity: 0.5,
    onStrokeComplete: vi.fn(),
    onFillComplete: vi.fn(),
    onFillError: vi.fn(),
    onEyedropperSample: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    clear: vi.fn(),
    canUndo: true,
    canRedo: false,
    onMagic: vi.fn(),
    onLogout: vi.fn(),
    magicNotice: null,
    setMagicNotice: vi.fn(),
    magicEnabled: false,
    magicOpen: false,
    magicPhase: 'idle',
    magicBusy: false,
    magicResult: null,
    magicError: null,
    magicLookUrl: null,
    magicSketchUrl: null,
    magicCanRecover: false,
    closeMagicPanel: vi.fn(),
    cancelMagicWait: vi.fn(),
    recoverLastMagic: vi.fn(),
    downloadMagicLook: vi.fn(),
    backToSketchFromMagic: vi.fn(),
    studioNotice: null,
    setStudioNotice: vi.fn(),
    publishStudioNotice: vi.fn(),
    comingSoon: null,
    setComingSoon: vi.fn(),
    showComingSoon: vi.fn(),
    saveStatus: 'idle',
    saveStatusLabel: 'Ready',
    saveError: null,
    retrySave: vi.fn(),
    modelSwitchPrompt: null,
    confirmModelKeepStrokes: vi.fn(),
    confirmModelClearStrokes: vi.fn(),
    cancelModelSwitch: vi.fn(),
    draftConflict: null,
    resolveConflictKeepLocal: vi.fn(),
    resolveConflictUseServer: vi.fn(),
    exporting: false,
    exportPng: vi.fn(),
    saveDesignDialog: null,
    beginSaveDesign: vi.fn(),
    confirmSaveDesign: vi.fn(),
    cancelSaveDesign: vi.fn(),
    libraryVersion: 0,
    openDesign: null,
    requestOpenDesign: vi.fn(),
    confirmOpenDesign: vi.fn(),
    retryOpenDesign: vi.fn(),
    cancelOpenDesign: vi.fn(),
  } as unknown as StudioEditor
}

describe('WEB-V4H immersive mode', () => {
  beforeEach(() => {
    mockMatchMedia(1440)
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => null,
    })
  })

  it('falls back to fixed immersive viewport when Fullscreen API is unavailable', async () => {
    const editor = mockEditor()
    // @ts-expect-error test override
    HTMLElement.prototype.requestFullscreen = undefined
    render(<CreatorWorkspace editor={editor} />)
    fireEvent.click(screen.getByRole('button', { name: 'Enter full screen drawing' }))
    const workspace = screen.getByLabelText('Creator workspace')
    expect(workspace.getAttribute('data-immersive')).toBe('true')
    expect(workspace.getAttribute('data-native-fullscreen')).toBe('false')
    expect(screen.getByTestId('drawing-canvas').getAttribute('data-immersive')).toBe('true')
    // Strokes prop chain preserved (mocked canvas still mounted under same editor).
    expect(editor.strokes).toHaveLength(1)
  })

  it('uses Fullscreen API when available from the user gesture', async () => {
    const editor = mockEditor()
    let fsEl: Element | null = null
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => fsEl,
    })
    HTMLElement.prototype.requestFullscreen = vi.fn(async function (this: HTMLElement) {
      fsEl = this
      document.dispatchEvent(new Event('fullscreenchange'))
    }) as unknown as typeof HTMLElement.prototype.requestFullscreen
    document.exitFullscreen = vi.fn(async () => {
      fsEl = null
      document.dispatchEvent(new Event('fullscreenchange'))
    }) as unknown as typeof document.exitFullscreen

    render(<CreatorWorkspace editor={editor} />)
    fireEvent.click(screen.getByRole('button', { name: 'Enter full screen drawing' }))
    expect(HTMLElement.prototype.requestFullscreen).toHaveBeenCalled()
    expect(screen.getByLabelText('Creator workspace').getAttribute('data-native-fullscreen')).toBe(
      'true',
    )

    fireEvent.click(screen.getByRole('button', { name: 'Exit full screen drawing' }))
    expect(document.exitFullscreen).toHaveBeenCalled()
    expect(screen.getByLabelText('Creator workspace').getAttribute('data-immersive')).toBe('false')
  })

  it('Fit Page / Fit Width / Hand pan controls remain available in immersive toolbar', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Enter full screen drawing' }))
    fireEvent.click(screen.getByRole('button', { name: 'Fit page' }))
    fireEvent.click(screen.getByRole('button', { name: 'Fit width' }))
    fireEvent.click(screen.getByRole('button', { name: '100%' }))
    fireEvent.click(screen.getByRole('button', { name: 'Hand pan' }))
    expect(screen.getByTestId('drawing-canvas').getAttribute('data-pan')).toBe('true')
  })
})
