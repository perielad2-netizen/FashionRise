import { useState, type ComponentProps } from 'react'
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

  it('keeps body measurement decimal separators while typing (Android inputMode decimal)', () => {
    const { onChangeSpec } = renderSheet()
    const height = screen.getByLabelText(/^Height$/i)
    expect(height).toHaveAttribute('inputMode', 'decimal')
    height.focus()
    fireEvent.change(height, { target: { value: '17' } })
    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '170.' } })
    expect(screen.getByLabelText(/^Height$/i)).toHaveValue('170.')
    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '170.5' } })
    expect(screen.getByLabelText(/^Height$/i)).toHaveValue('170.5')
    expect(onChangeSpec).toHaveBeenCalled()
    expect(baseSpec.body?.height).toMatchObject({ value: 170.5, source: 'designer' })
  })

  it('keeps finished POM decimals and marks AI edits as designer', () => {
    const aiPiece: TechpackPiece = {
      ...piece,
      finished_measurements: {
        chest_bust: { value: null, unit: 'cm', source: 'empty' },
        garment_length: {
          value: 110,
          unit: 'cm',
          source: 'ai',
          review_status: 'open',
        },
      },
    }
    const aiSpec: TechpackSpecV2 = {
      ...baseSpec,
      outfit: { piece_count: 1, pieces: [aiPiece] },
    }
    const { onUpdatePiece } = renderSheet({ spec: aiSpec, pieces: [aiPiece] })
    fireEvent.click(screen.getByRole('tab', { name: /Finished · /i }))
    const length = screen.getByLabelText(/Garment length/i)
    expect(length).toHaveAttribute('inputMode', 'decimal')
    length.focus()
    fireEvent.change(length, { target: { value: '110.' } })
    expect(screen.getByLabelText(/Garment length/i)).toHaveValue('110.')
    fireEvent.change(screen.getByLabelText(/Garment length/i), { target: { value: '110.25' } })
    expect(screen.getByLabelText(/Garment length/i)).toHaveValue('110.25')
    expect(onUpdatePiece).toHaveBeenCalled()
    const lastCall = onUpdatePiece.mock.calls.at(-1)
    expect(lastCall?.[0]).toBe('piece-1')
    const updated = lastCall?.[1](aiPiece) as TechpackPiece
    expect(updated.finished_measurements.garment_length).toMatchObject({
      value: 110.25,
      source: 'designer',
      review_status: 'open',
    })
  })

  it('keeps unit/source behind a secondary toggle for everyday entry', () => {
    renderSheet()
    expect(screen.queryByLabelText(/^Height unit$/i)).not.toBeInTheDocument()
    const toggles = screen.getAllByRole('button', { name: /Unit \/ source/i })
    expect(toggles.length).toBeGreaterThan(0)
    fireEvent.click(toggles[0])
    expect(screen.getByLabelText(/^Height unit$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^Height source$/i)).toBeInTheDocument()
  })

  it('accepts typed waist values without inventing units', () => {
    renderSheet()
    const waist = screen.getByLabelText(/^Waist$/i)
    fireEvent.change(waist, { target: { value: '80' } })
    expect(waist).toHaveValue('80')
    expect(screen.getAllByText('cm').length).toBeGreaterThan(0)
  })

  it('keeps Finished Dress selected after each keystroke when pieces identity changes', () => {
    const shirt: TechpackPiece = {
      id: 'shirt-1',
      category: 'top',
      role: 'TOP',
      label: 'Shirt',
      finished_measurements: {
        chest_bust: { value: null, unit: 'cm', source: 'empty' },
        sleeve_length: { value: null, unit: 'cm', source: 'empty' },
      },
    }
    const trousers: TechpackPiece = {
      id: 'trousers-1',
      category: 'bottom',
      role: 'BOTTOM',
      label: 'Trousers',
      finished_measurements: {
        waist: { value: null, unit: 'cm', source: 'empty' },
        inseam: { value: null, unit: 'cm', source: 'empty' },
        garment_length: { value: null, unit: 'cm', source: 'empty' },
      },
    }
    const dress: TechpackPiece = {
      ...piece,
      finished_measurements: {
        chest_bust: { value: null, unit: 'cm', source: 'empty' },
        waist: { value: null, unit: 'cm', source: 'empty' },
        hip: { value: null, unit: 'cm', source: 'empty' },
        garment_length: { value: null, unit: 'cm', source: 'empty' },
        hem_circumference: { value: null, unit: 'cm', source: 'empty' },
      },
    }

    function Harness({ multi }: { multi?: boolean }) {
      const [spec, setSpec] = useState<TechpackSpecV2>(() => ({
        ...baseSpec,
        outfit: {
          piece_count: multi ? 2 : 1,
          pieces: multi ? [shirt, trousers] : [dress],
        },
      }))
      const pieces = spec.outfit?.pieces ?? []
      return (
        <MeasurementsSheet
          open
          draftKey="draft-1"
          initialGroupId={multi ? 'piece:trousers-1' : 'piece:piece-1'}
          spec={spec}
          pieces={pieces}
          onChangeSpec={(updater) => setSpec((prev) => updater(prev))}
          onUpdatePiece={(pieceId, updater) => {
            // Mirror TechpackScreen: always allocate a new pieces array.
            setSpec((prev) => {
              const nextPieces = (prev.outfit?.pieces ?? []).map((p) =>
                p.id === pieceId ? updater({ ...p }) : p,
              )
              return {
                ...prev,
                outfit: {
                  ...(prev.outfit ?? { piece_count: nextPieces.length, pieces: nextPieces }),
                  piece_count: nextPieces.length,
                  pieces: nextPieces.map((p) => ({ ...p })),
                },
              }
            })
          }}
          onSaveAndDone={() => undefined}
          onDiscardAndClose={() => undefined}
        />
      )
    }

    render(<Harness />)
    const dialog = screen.getByRole('dialog', { name: /Finished · /i })
    expect(dialog).toBeInTheDocument()
    expect(screen.getByText(/Group 3 of 3/i)).toBeInTheDocument()

    const fieldByName = (name: RegExp) => {
      const matches = screen.getAllByLabelText(name).filter((el) => el.tagName === 'INPUT')
      expect(matches.length).toBeGreaterThan(0)
      return matches[0] as HTMLInputElement
    }

    const fields = [
      [/Chest \/ bust/i, '88'],
      [/^Waist$/i, '70'],
      [/^Hip$/i, '94'],
      [/Garment length/i, '112'],
      [/hem circumference/i, '120'],
    ] as const

    for (const [label, value] of fields) {
      let input = fieldByName(label)
      input.focus()
      expect(document.activeElement).toBe(input)
      let typed = ''
      for (const ch of value) {
        typed += ch
        fireEvent.change(input, { target: { value: typed } })
        expect(screen.getByRole('dialog', { name: /Finished · /i })).toBeInTheDocument()
        expect(screen.getByText(/Group 3 of 3/i)).toBeInTheDocument()
        input = fieldByName(label)
        expect(input).toHaveValue(typed)
        expect(document.activeElement).toBe(input)
      }
    }

    fireEvent.click(screen.getByRole('tab', { name: /^Preferences$/i }))
    expect(screen.getByRole('dialog', { name: /Preferences/i })).toBeInTheDocument()
    const sample = screen.getByLabelText(/Sample size/i) as HTMLInputElement
    sample.focus()
    fireEvent.change(sample, { target: { value: '36' } })
    expect(screen.getByRole('dialog', { name: /Preferences/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/Sample size/i)).toHaveValue('36')
    expect(document.activeElement).toBe(screen.getByLabelText(/Sample size/i))

    cleanup()
    render(<Harness multi />)
    expect(screen.getByRole('dialog', { name: /Finished · /i })).toBeInTheDocument()
    // shirt + trousers → groups: body, preferences, shirt, trousers = 4; start on trousers
    expect(screen.getByText(/Group 4 of 4/i)).toBeInTheDocument()
    const waist = fieldByName(/^Waist$/i)
    waist.focus()
    fireEvent.change(waist, { target: { value: '72' } })
    expect(screen.getByText(/Group 4 of 4/i)).toBeInTheDocument()
    expect(fieldByName(/^Waist$/i)).toHaveValue('72')
    expect(document.activeElement).toBe(fieldByName(/^Waist$/i))
  })
})
