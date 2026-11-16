import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { fabricStyle, solidStyle } from '@/lib/fills'

vi.mock('@/services/fabricAssetsApi', () => ({
  listMyFabrics: vi.fn(async () => []),
  uploadFabric: vi.fn(),
  createAiFabric: vi.fn(),
  deleteFabric: vi.fn(),
  fetchFabricImageBlob: vi.fn(),
}))

vi.mock('@/hooks/useAiStarsWallet', () => ({
  useAiStarsWallet: () => ({
    balance: 100,
    unlimited: false,
    costs: { fabric: 2, croquis: 5, magic: 10, techpack: 15 },
    refresh: vi.fn(),
  }),
}))

vi.mock('@/lib/defaultFabricTiles', () => ({
  preloadDefaultFabricTiles: vi.fn(async () => undefined),
}))

vi.mock('@/shell/components/StarsShopModal', () => ({
  StarsShopModal: () => null,
}))

vi.mock('@/shell/components/AiSpendConfirmDialog', () => ({
  AiSpendConfirmDialog: () => null,
}))

describe('ColorAndMaterialsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens the professional picker, applies color, and keeps fabrics/gradients', async () => {
    const onColor = vi.fn()
    const onColorHex = vi.fn(() => true)
    const onFillStyle = vi.fn()
    const onToggleEyedropper = vi.fn()

    render(
      <ColorAndMaterialsPanel
        color="#1C1C1E"
        onColor={onColor}
        onColorHex={onColorHex}
        fillStyle={solidStyle('#1C1C1E')}
        onFillStyle={onFillStyle}
        eyedropperActive={false}
        onToggleEyedropper={onToggleEyedropper}
      />,
    )

    expect(screen.getByRole('tab', { name: 'Colors' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Fabrics' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Gradients' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Crimson' }))
    expect(onColor).toHaveBeenCalledWith('#B91C1C')

    fireEvent.click(screen.getAllByRole('button', { name: 'Choose any color' })[0]!)
    const picker = screen.getByRole('dialog', { name: 'Choose color' })
    expect(picker).toBeTruthy()
    const pickerHex = screen.getByRole('dialog', { name: 'Choose color' }).querySelector(
      'input[aria-label="Hex color"]',
    ) as HTMLInputElement
    fireEvent.change(pickerHex, { target: { value: '#0f766e' } })
    fireEvent.blur(pickerHex)
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onColor).toHaveBeenCalledWith('#0F766E')

    fireEvent.click(screen.getByRole('button', { name: 'Eyedropper' }))
    expect(onToggleEyedropper).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('tab', { name: 'Fabrics' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Create with AI/i })).toBeTruthy())
    expect(screen.getByRole('button', { name: /Upload/i })).toBeTruthy()
    fireEvent.click(screen.getByTestId('fabric-preset-blue-denim'))
    expect(onFillStyle).toHaveBeenCalledWith({
      kind: 'fabric',
      fabricId: 'blue-denim',
      scale: 1,
    })
    expect(screen.getByTestId('fabrics-all-grid')).toBeTruthy()
    expect(screen.getByTestId('fabric-preset-white-silk')).toBeTruthy()
    expect(screen.getByTestId('fabric-preset-black-cotton')).toBeTruthy()
    expect(screen.getByTestId('fabric-preset-brown-corduroy')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Gradients' }))
    const rose = screen.getByRole('button', { name: 'Rose violet' })
    expect(rose.textContent).toMatch(/Rose violet/i)
    fireEvent.click(rose)
    expect(onFillStyle).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'gradient', gradientId: 'rose-violet' }),
    )
  })

  it('shows pattern scale with live preview for every selected fabric', () => {
    const onFillStyle = vi.fn()
    render(
      <ColorAndMaterialsPanel
        color="#1C1C1E"
        onColor={() => undefined}
        onColorHex={() => true}
        fillStyle={fabricStyle('blue-denim', 1)!}
        onFillStyle={onFillStyle}
        eyedropperActive={false}
        onToggleEyedropper={() => undefined}
      />,
    )
    fireEvent.click(screen.getByRole('tab', { name: 'Fabrics' }))
    expect(screen.getByTestId('fabric-scale-block')).toBeTruthy()
    expect(screen.getByTestId('fabric-scale-preview')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Fine' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Coarse' }))
    expect(onFillStyle).toHaveBeenCalledWith({
      kind: 'fabric',
      fabricId: 'blue-denim',
      scale: 2,
    })
  })

  it('cancels the professional picker without committing', () => {
    const onColor = vi.fn()
    render(
      <ColorAndMaterialsPanel
        color="#ABCDEF"
        onColor={onColor}
        onColorHex={() => true}
        fillStyle={solidStyle('#ABCDEF')}
        onFillStyle={() => undefined}
        eyedropperActive={false}
        onToggleEyedropper={() => undefined}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Open color picker' }))
    const pickerHex = screen.getByRole('dialog', { name: 'Choose color' }).querySelector(
      'input[aria-label="Hex color"]',
    ) as HTMLInputElement
    fireEvent.change(pickerHex, { target: { value: '#112233' } })
    fireEvent.blur(pickerHex)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onColor).not.toHaveBeenCalled()
  })
})
