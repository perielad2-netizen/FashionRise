/**
 * Regression: Done button stays the only footer chrome (no Saving/Saved status line).
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useState } from 'react'
import { DetailsEditorSheet } from '@/shell/components/techpack/DetailsEditorSheet'
import type { TechpackPiece, TechpackSpecV2 } from '@/services/techpacksApi'

const BASE_SPEC: TechpackSpecV2 = {
  schema_version: '2.0',
  units: 'cm',
  size_system: 'EU',
  sample_size: '',
  look_notes: '',
  designer_notes: '',
  outfit: {
    piece_count: 2,
    pieces: [
      {
        id: 'piece-shirt',
        category: 'shirt',
        label: 'Black shirt',
        materials: { shell: { name: '', source: 'empty' } },
        closures: { type: '', source: 'empty' },
        fit: { silhouette: '' },
        finished_measurements: {
          chest_bust: { value: null, unit: 'cm', source: 'empty' },
        },
      },
      {
        id: 'piece-trousers',
        category: 'trousers',
        label: 'Beige trousers',
        materials: { shell: { name: '', source: 'empty' } },
        closures: { type: '', source: 'empty' },
        fit: { silhouette: '' },
        finished_measurements: {
          waist: { value: null, unit: 'cm', source: 'empty' },
        },
      },
    ],
  },
  body: {
    height: { value: null, unit: 'cm', source: 'empty' },
    waist: { value: null, unit: 'cm', source: 'empty' },
  },
  preferences: { fit_preference: 'regular', notes: '' },
}

function Harness({
  busy = false,
  saveError = null as string | null,
}: {
  busy?: boolean
  saveError?: string | null
}) {
  const [spec, setSpec] = useState(BASE_SPEC)
  const pieces = (spec.outfit?.pieces ?? []) as TechpackPiece[]
  return (
    <DetailsEditorSheet
      open
      draftKey="draft-stability"
      title="Black shirt set"
      styleCode="FR-TEST"
      spec={spec}
      pieces={pieces}
      busy={busy}
      saveError={saveError}
      lookThumbnailUrl="blob:magic-look"
      onChangeTitle={() => undefined}
      onChangeStyleCode={() => undefined}
      onChangeSpec={(updater) => setSpec((prev) => updater(prev))}
      onUpdatePiece={(pieceId, updater) =>
        setSpec((prev) => {
          const list = [...(prev.outfit?.pieces ?? [])]
          const idx = list.findIndex((p) => p.id === pieceId)
          if (idx < 0) return prev
          list[idx] = updater(list[idx] as TechpackPiece)
          return {
            ...prev,
            outfit: { ...(prev.outfit ?? { piece_count: list.length, pieces: list }), pieces: list },
          }
        })
      }
      onClose={() => undefined}
    />
  )
}

describe('DetailsEditorSheet quiet footer', () => {
  it('shows only Done in the footer when save is healthy', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 })
    render(<Harness />)
    const done = await screen.findByTestId('details-done')
    expect(done).toHaveTextContent('Done')
    expect(done.className).toMatch(/doneBtn/)
    expect(done.parentElement?.className).toMatch(/footerStack/)
    expect(screen.queryByText(/Saving/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Saved$/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Edits save automatically/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/autosave on/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Measurements & details/i })).toBeInTheDocument()
  })

  it('surfaces save failure without routine status messaging', async () => {
    render(<Harness saveError="network down" />)
    expect(await screen.findByTestId('details-save-error')).toHaveTextContent(/network down/i)
    expect(screen.getByTestId('details-done')).toHaveTextContent('Done')
    expect(screen.queryByText(/Saving/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Saved$/i)).not.toBeInTheDocument()
  })
})
