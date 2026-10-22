import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { solidStyle } from '@/lib/fills'

vi.mock('@/services/fabricAssetsApi', () => ({
  listMyFabrics: vi.fn(async () => []),
  uploadFabric: vi.fn(),
  deleteFabric: vi.fn(),
  fetchFabricImageBlob: vi.fn(),
}))

describe('ColorAndMaterialsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exposes fashion palette, native picker, fabrics, add fabric and gradients', async () => {
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

    await waitFor(() => expect(screen.getByRole('button', { name: /Add Fabric/i })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Crimson' }))
    expect(onColor).toHaveBeenCalledWith('#B91C1C')

    fireEvent.change(screen.getByLabelText('Color picker'), { target: { value: '#0f766e' } })
    expect(onColor).toHaveBeenCalledWith('#0F766E')

    fireEvent.click(screen.getByRole('button', { name: 'Denim' }))
    expect(onFillStyle).toHaveBeenCalledWith({ kind: 'fabric', fabricId: 'denim' })

    fireEvent.click(screen.getByRole('button', { name: 'Rose violet' }))
    expect(onFillStyle).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'gradient', gradientId: 'rose-violet' }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Eyedropper' }))
    expect(onToggleEyedropper).toHaveBeenCalled()

    expect(screen.getByText(/My Fabrics/i)).toBeTruthy()
  })
})
