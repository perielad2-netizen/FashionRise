import type { ComponentProps } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MeasurementsSheet } from './MeasurementsSheet'
import type { TechpackPiece, TechpackSpecV2 } from '@/services/techpacksApi'

type SheetProps = ComponentProps<typeof MeasurementsSheet>

const piece: TechpackPiece = {
  id: 'piece-1',
  category: 'dress',
  role: 'ONE_PIECE',
  label: 'Pink dress',
  finished_measurements: {
    chest_bust: { value: null, unit: 'cm', source: 'empty' },
    garment_length: { value: 110, unit: 'cm', source: 'estimate' },
  },
}

const baseSpec: TechpackSpecV2 = {
  schema_version: '2.0',
  units: 'cm',
  body: {
    height: { value: null, unit: 'cm', source: 'empty' },
    bust: { value: null, unit: 'cm', source: 'empty' },
  },
  preferences: { fit_preference: 'regular', notes: '' },
  outfit: { piece_count: 1, pieces: [piece] },
}

function renderSheet(overrides: Partial<SheetProps> = {}) {
  const onChangeSpec = vi.fn((updater: (prev: TechpackSpecV2) => TechpackSpecV2) => {
    Object.assign(baseSpec, updater(baseSpec))
  })
  const onUpdatePiece = vi.fn()
  const onSaveAndDone = vi.fn()
  const onDiscardAndClose = vi.fn()
  render(
    <MeasurementsSheet
      open
      spec={baseSpec}
      pieces={[piece]}
      onChangeSpec={onChangeSpec}
      onUpdatePiece={onUpdatePiece}
      onSaveAndDone={onSaveAndDone}
      onDiscardAndClose={onDiscardAndClose}
      {...overrides}
    />,
  )
  return { onChangeSpec, onUpdatePiece, onSaveAndDone, onDiscardAndClose }
}

describe('MeasurementsSheet', () => {
  beforeEach(() => {
    document.body.style.overflow = ''
  })
  afterEach(() => {
    cleanup()
  })

  it('shows one logical group at a time with sticky Save & Done', () => {
    renderSheet()
    const dialog = screen.getByRole('dialog', { name: /Body measurements/i })
    expect(dialog).toBeInTheDocument()
    expect(screen.getByText(/Group 1 of 3/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save & Done/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Next/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    expect(screen.getByRole('dialog', { name: /Preferences/i })).toBeInTheDocument()
  })

  it('allows empty unknown measurements and does not invent values', () => {
    renderSheet()
    const height = screen.getByLabelText(/^Height$/i)
    expect(height).toHaveValue('')
    fireEvent.change(height, { target: { value: '' } })
    expect(height).toHaveValue('')
  })

  it('preserves garment finished tabs as separate groups', () => {
    renderSheet()
    fireEvent.click(screen.getByRole('tab', { name: /Finished · /i }))
    expect(screen.getByText(/Chest \/ bust|chest/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('110')).toBeInTheDocument()
  })

  it('asks before discarding dirty edits', () => {
    const { onDiscardAndClose } = renderSheet()
    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '170' } })
    fireEvent.click(screen.getByRole('button', { name: /Close measurements editor/i }))
    expect(onDiscardAndClose).not.toHaveBeenCalled()
    expect(screen.getByText(/Discard unsaved measurement edits/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Discard$/i }))
    expect(onDiscardAndClose).toHaveBeenCalled()
  })

  it('Save & Done calls save handler', () => {
    const { onSaveAndDone } = renderSheet()
    fireEvent.click(screen.getByRole('button', { name: /Save & Done/i }))
    expect(onSaveAndDone).toHaveBeenCalled()
  })

  it('uses large touch-friendly decimal inputs', () => {
    renderSheet()
    const height = screen.getByLabelText(/^Height$/i)
    expect(height).toHaveAttribute('inputMode', 'decimal')
  })
})
