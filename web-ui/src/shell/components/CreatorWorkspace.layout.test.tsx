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
    canUndo: false,
    canRedo: false,
    onMagic: vi.fn(),
    onLogout: vi.fn(),
    magicNotice: null,
    setMagicNotice: vi.fn(),
    magicEnabled: true,
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
    damagedCloud: null,
    damagedCloudDialogOpen: false,
    resolveDamagedCloudContinueLocal: vi.fn(),
    resolveDamagedCloudReplaceCloud: vi.fn(),
    reopenDamagedCloudRecovery: vi.fn(),
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

describe('CreatorWorkspace tablet layout controls (WEB-V4I)', () => {
  beforeEach(() => {
    mockMatchMedia(768)
  })

  it('does not expose Focus entry points; Full screen remains available', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const workspace = screen.getByLabelText('Creator workspace')
    const dock = within(screen.getByLabelText('Studio panels'))
    expect(workspace.className).not.toMatch(/focusMode/)
    expect(screen.queryByRole('button', { name: /Focus|Exit focus|focused sketch/i })).toBeNull()
    expect(dock.getByRole('button', { name: 'Full screen' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Enter full screen drawing' })).toBeTruthy()
  })

  it('opens Models as an overlay gallery with Done/scrim (does not rely on Focus)', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const dock = within(screen.getByLabelText('Studio panels'))
    fireEvent.click(dock.getByRole('button', { name: 'Models' }))
    expect(screen.getByRole('dialog', { name: 'Models gallery' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Done' })).toBeTruthy()
    expect(screen.getByLabelText('Close panel')).toBeTruthy()
    const library = screen.getByLabelText('Model library')
    expect(library.getAttribute('data-variant')).toBe('gallery')
    expect(within(library).getByRole('tab', { name: 'Female' })).toBeTruthy()
    expect(within(library).getByRole('tab', { name: 'Male' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('dialog', { name: 'Models gallery' })).toBeNull()
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

  it('Escape closes the materials sheet before exiting immersive', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const dock = within(screen.getByLabelText('Studio panels'))
    fireEvent.click(dock.getByRole('button', { name: 'Full screen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Materials' }))
    expect(screen.getByLabelText('Close panel')).toBeTruthy()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByLabelText('Close panel')).toBeNull()
    expect(screen.getByLabelText('Creator workspace').getAttribute('data-immersive')).toBe('true')

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.getByLabelText('Creator workspace').getAttribute('data-immersive')).toBe('false')
  })

  it('enters immersive drawing from normal Studio and exits via Escape', async () => {
    const editor = mockEditor()
    render(<CreatorWorkspace editor={editor} />)
    const workspace = screen.getByLabelText('Creator workspace')
    const dock = within(screen.getByLabelText('Studio panels'))

    fireEvent.click(dock.getByRole('button', { name: 'Full screen' }))
    expect(workspace.getAttribute('data-immersive')).toBe('true')
    expect(workspace.className).toMatch(/immersiveMode/)
    expect(workspace.className).not.toMatch(/focusMode/)
    expect(screen.getByRole('toolbar', { name: 'Immersive drawing toolbar' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Fit width' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Hand pan' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Models' }))
    expect(screen.getByRole('dialog', { name: 'Models gallery' })).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Models gallery' })).toBeNull()
    expect(workspace.getAttribute('data-immersive')).toBe('true')

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(workspace.getAttribute('data-immersive')).toBe('false')
    expect(workspace.className).not.toMatch(/immersiveMode/)
  })

  it('Settings does not show obsolete Generate with AI Soon footer', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const dock = within(screen.getByLabelText('Studio panels'))
    fireEvent.click(dock.getByRole('button', { name: 'Settings' }))
    const settings = screen.getByLabelText(/settings inspector/i)
    expect(within(settings).queryByText('Generate with AI')).toBeNull()
    expect(within(settings).queryByText('Soon')).toBeNull()
    // Real Magic remains in the Studio header (Soon badge there is separate / env-gated).
    expect(screen.getByRole('button', { name: /Magic/i })).toBeTruthy()
  })

  it('moves keyboard focus into Models gallery and restores the Models button on Done / Escape / scrim', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    const modelsBtn = within(screen.getByLabelText('Studio panels')).getByRole('button', {
      name: 'Models',
    })
    modelsBtn.focus()
    fireEvent.click(modelsBtn)

    const dialog = screen.getByRole('dialog', { name: 'Models gallery' })
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: 'Done' }))

    fireEvent.click(within(dialog).getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('dialog', { name: 'Models gallery' })).toBeNull()
    expect(document.activeElement).toBe(modelsBtn)

    modelsBtn.focus()
    fireEvent.click(modelsBtn)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Models gallery' })).toBeNull()
    expect(document.activeElement).toBe(modelsBtn)

    modelsBtn.focus()
    fireEvent.click(modelsBtn)
    fireEvent.click(screen.getByLabelText('Close panel'))
    expect(screen.queryByRole('dialog', { name: 'Models gallery' })).toBeNull()
    expect(document.activeElement).toBe(modelsBtn)
  })

  it('keeps Tab / Shift+Tab cycling inside the open Models gallery', () => {
    render(<CreatorWorkspace editor={mockEditor()} />)
    fireEvent.click(
      within(screen.getByLabelText('Studio panels')).getByRole('button', { name: 'Models' }),
    )
    const dialog = screen.getByRole('dialog', { name: 'Models gallery' })
    const first = within(dialog).getByRole('button', { name: 'Done' })
    const cards = within(dialog).getAllByRole('button', { name: /Select .+ reference/i })
    const last = cards[cards.length - 1]!

    first.focus()
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)

    last.focus()
    fireEvent.keyDown(window, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
  })

  it('gives model-switch confirmation precedence for focus and Escape over Models gallery', () => {
    const { rerender } = render(<CreatorWorkspace editor={mockEditor()} />)
    const modelsBtn = within(screen.getByLabelText('Studio panels')).getByRole('button', {
      name: 'Models',
    })
    modelsBtn.focus()
    fireEvent.click(modelsBtn)
    expect(screen.getByRole('dialog', { name: 'Models gallery' })).toBeTruthy()
    expect(document.activeElement).toBe(
      within(screen.getByRole('dialog', { name: 'Models gallery' })).getByRole('button', {
        name: 'Done',
      }),
    )

    rerender(
      <CreatorWorkspace
        editor={mockEditor({
          modelSwitchPrompt: { next: 'blank' },
        })}
      />,
    )

    const confirm = screen.getByRole('dialog', { name: 'Change reference model?' })
    expect(confirm.contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toBe(
      within(confirm).getByRole('button', { name: 'Keep strokes' }),
    )

    fireEvent.keyDown(window, { key: 'Escape' })
    // Confirm has no onEscape — Escape must not dismiss Models underneath.
    expect(screen.getByRole('dialog', { name: 'Models gallery' })).toBeTruthy()
    expect(screen.getByRole('dialog', { name: 'Change reference model?' })).toBeTruthy()
  })
})
