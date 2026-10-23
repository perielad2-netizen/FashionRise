import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
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
  DrawingCanvas: () => <div data-testid="drawing-canvas">canvas</div>,
}))

function mockMatchMedia(width: number) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => {
    const max = /max-width:\s*(\d+)px/.exec(query)
    const min = /min-width:\s*(\d+)px/.exec(query)
    let matches = false
    if (max) matches = width <= Number(max[1])
    if (min) matches = width >= Number(min[1])
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

function mockEditor(overrides: Partial<StudioEditor> = {}): StudioEditor {
  const base = {
    user: { id: 'u1', username: 'Tester' },
    ready: true,
    strokes: [],
    fills: [],
    tool: 'draw',
    setTool: vi.fn(),
    sizeId: 'medium' as const,
    setSizeId: vi.fn(),
    brushSize: BRUSH_SIZES.medium,
    setBrushSizePx: vi.fn(),
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
    canUndo: false,
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
    magicNoticeText: '',
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
  }
  return { ...base, ...overrides } as unknown as StudioEditor
}

describe('CreatorWorkspace tablet layout controls', () => {
  beforeEach(() => {
    mockMatchMedia(768)
  })

  it('enters focus mode, exposes panel shortcuts, and exits via dock control', () => {
    const { container } = render(<CreatorWorkspace editor={mockEditor()} />)
    const workspace = screen.getByLabelText('Creator workspace')
    const dock = within(screen.getByLabelText('Studio panels'))
    expect(workspace.className).not.toMatch(/focusMode/)

    fireEvent.click(dock.getByRole('button', { name: 'Focus' }))
    expect(workspace.className).toMatch(/focusMode/)
    // Tablet dock already exposes Models/Materials/Settings — avoid a second toolbar.
    expect(screen.queryByLabelText('Focus mode panels')).toBeNull()
    expect(dock.getByRole('button', { name: 'Materials' })).toBeTruthy()
    expect(container.querySelector('[data-studio-paper="true"]')).toBeTruthy()

    fireEvent.click(dock.getByRole('button', { name: 'Exit focus' }))
    expect(workspace.className).not.toMatch(/focusMode/)
  })

  it('opens a bounded materials sheet with Done and keeps tabs switchable', async () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const dock = within(screen.getByLabelText('Studio panels'))
    fireEvent.click(dock.getByRole('button', { name: 'Materials' }))
    expect(screen.getByRole('button', { name: 'Done' })).toBeTruthy()
    expect(screen.getByLabelText('Close panel')).toBeTruthy()

    const materials = screen.getByLabelText('Colors and materials')
    fireEvent.click(within(materials).getByRole('tab', { name: 'Fabrics' }))
    expect(within(materials).getByRole('tabpanel', { name: 'Fabrics' })).toBeTruthy()
    fireEvent.click(within(materials).getByRole('tab', { name: 'Gradients' }))
    expect(within(materials).getByRole('tabpanel', { name: 'Gradients' })).toBeTruthy()
    fireEvent.click(within(materials).getByRole('tab', { name: 'Colors' }))
    expect(within(materials).getByRole('tabpanel', { name: 'Colors' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByLabelText('Close panel')).toBeNull()
  })

  it('Escape closes the materials sheet before exiting focus', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const dock = within(screen.getByLabelText('Studio panels'))
    fireEvent.click(dock.getByRole('button', { name: 'Focus' }))
    fireEvent.click(dock.getByRole('button', { name: 'Materials' }))
    expect(screen.getByLabelText('Close panel')).toBeTruthy()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByLabelText('Close panel')).toBeNull()
    expect(screen.getByLabelText('Creator workspace').className).toMatch(/focusMode/)

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.getByLabelText('Creator workspace').className).not.toMatch(/focusMode/)
  })
})
