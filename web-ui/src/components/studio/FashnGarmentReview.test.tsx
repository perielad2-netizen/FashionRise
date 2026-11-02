import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { FashnGarmentReview } from './FashnGarmentReview'
import type { FashnGarmentPrepareResult, FashnRealisticPiece } from '@/services/ai/magicApi'
import { ConfirmDialog } from './ConfirmDialog'

const TINY =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

function prep(overrides: Partial<FashnGarmentPrepareResult> = {}): FashnGarmentPrepareResult {
  return {
    provider: 'fashn',
    configured: true,
    live_http: true,
    openai_live_http: true,
    quality_ok: true,
    quality_notes: '',
    layout: 'two_piece',
    pieces: [
      { category: 'tops', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
      { category: 'bottoms', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
    ],
    composite_preview_base64: TINY,
    garment_fingerprint: 'fp-test',
    fashn_calls: 2,
    estimate_cents: 16,
    realism_estimate_cents: 16,
    realism_calls: 2,
    combined_estimate_cents: 32,
    consent_version: 'try-on-fashn-oneclick-v1',
    notice_text: 'FASHN notice',
    notice_hash: 'nh',
    notes: 'notes',
    ...overrides,
  }
}

describe('FashnGarmentReview (#169)', () => {
  it('shows sketch top/bottom separately and opens enlarged preview', () => {
    render(
      <FashnGarmentReview
        prep={prep()}
        realisticPieces={null}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
      />,
    )
    const sketch = screen.getByTestId('fashn-sketch-pieces')
    expect(sketch).toHaveAttribute('data-layout', 'two_piece')
    expect(screen.getByText('Top')).toBeInTheDocument()
    expect(screen.getByText('Bottom')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Enlarge Top sketch'))
    expect(screen.getByTestId('fashn-piece-lightbox')).toBeInTheDocument()
  })

  it('shows realistic pieces and hard fidelity failure copy', () => {
    const pieces: FashnRealisticPiece[] = [
      {
        category: 'tops',
        image_base64: TINY,
        fidelity: { ok: true, code: 'FIDELITY_OK' },
      },
      {
        category: 'bottoms',
        image_base64: TINY,
        fidelity: {
          ok: false,
          code: 'FIDELITY_COVERAGE_EXPANDED',
          message: 'Bottoms coverage expanded.',
        },
      },
    ]
    render(
      <FashnGarmentReview
        prep={prep()}
        realisticPieces={pieces}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
      />,
    )
    expect(screen.getByTestId('fashn-realistic-pieces')).toBeInTheDocument()
    expect(screen.getByTestId('fashn-fidelity-hard-fail')).toHaveTextContent(
      'Bottoms coverage expanded.',
    )
    expect(screen.getByTestId('fashn-cost-summary').textContent).toMatch(/OpenAI/)
    expect(screen.getByTestId('fashn-cost-summary').textContent).toMatch(/FASHN/)
  })

  it('one-piece layout labels a single garment', () => {
    render(
      <FashnGarmentReview
        prep={prep({
          layout: 'one_piece',
          pieces: [
            { category: 'one-pieces', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
          ],
          fashn_calls: 1,
          estimate_cents: 8,
          realism_calls: 1,
          realism_estimate_cents: 8,
          combined_estimate_cents: 16,
        })}
        realisticPieces={[
          { category: 'one-pieces', image_base64: TINY, fidelity: { ok: true, code: 'FIDELITY_OK' } },
        ]}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
      />,
    )
    expect(screen.getByTestId('fashn-sketch-pieces')).toHaveAttribute('data-layout', 'one_piece')
    expect(screen.getAllByText('Garment').length).toBeGreaterThan(0)
  })
})

describe('FASHN Accept dialog actions (#169)', () => {
  it('disables Accept on hard fidelity failure; Cancel and Regenerate stay available', () => {
    const onCancel = vi.fn()
    const onRegen = vi.fn()
    const onAccept = vi.fn()
    const pieces: FashnRealisticPiece[] = [
      {
        category: 'one-pieces',
        image_base64: TINY,
        fidelity: { ok: false, code: 'FIDELITY_COVERAGE_EXPANDED', message: 'fail' },
      },
    ]
    render(
      <ConfirmDialog
        title="Accept realistic garment"
        scrollable
        onEscape={onCancel}
        actions={[
          { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
          { label: 'Regenerate Garment', onClick: onRegen, variant: 'ghost' },
          {
            label: 'Accept & Try On',
            onClick: onAccept,
            disabled: pieces.some((p) => p.fidelity && p.fidelity.ok === false),
          },
        ]}
      >
        <FashnGarmentReview
          prep={prep({
            layout: 'one_piece',
            pieces: [
              {
                category: 'one-pieces',
                image_base64: TINY,
                bbox: [0, 0, 10, 10],
                opaque_pixels: 40,
              },
            ],
          })}
          realisticPieces={pieces}
          realismBusy={false}
          realismError={null}
          detailsOpen={false}
          onToggleDetails={() => undefined}
        />
      </ConfirmDialog>,
    )
    expect(screen.getByRole('button', { name: 'Accept & Try On' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Regenerate Garment' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onAccept).not.toHaveBeenCalled()
  })

  it('keeps Accept enabled when fidelity passes; action labels have no prices', () => {
    render(
      <ConfirmDialog
        title="Accept realistic garment"
        scrollable
        actions={[
          { label: 'Cancel', onClick: () => undefined, variant: 'ghost' },
          { label: 'Regenerate Garment', onClick: () => undefined, variant: 'ghost' },
          { label: 'Accept & Try On', onClick: () => undefined },
        ]}
      >
        <span>body</span>
      </ConfirmDialog>,
    )
    const accept = screen.getByRole('button', { name: 'Accept & Try On' })
    expect(accept).toBeEnabled()
    expect(accept.textContent).not.toMatch(/¢/)
    expect(screen.getByRole('button', { name: 'Regenerate Garment' }).textContent).not.toMatch(/¢/)
  })
})

const experimentBase = {
  mode: 'balanced' as const,
  onModeChange: () => undefined,
  resolution: '1k' as const,
  onResolutionChange: () => undefined,
  prompt: '',
  onPromptChange: () => undefined,
  promptOpen: false,
  onTogglePrompt: () => undefined,
  softBudgetCredits: 90,
  creditsBalanced: 2,
  creditsQuality: 3,
  estimateBalancedCents: 16,
  estimateQualityCents: 24,
  v16Category: 'one-pieces' as const,
  onV16CategoryChange: () => undefined,
  v16SegmentationFree: true,
  onV16SegmentationFreeChange: () => undefined,
  v16Mode: 'balanced' as const,
  onV16ModeChange: () => undefined,
  v16Seed: 42,
  onV16SeedChange: () => undefined,
  acceptedOptions: [
    {
      jobId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      label: 'accepted · one-pieces',
      pieceCount: 1,
      categories: ['one-pieces'],
    },
  ],
  selectedAcceptedJobId: null as string | null,
  onSelectAcceptedJobId: () => undefined,
  onLoadAcceptedJob: () => undefined,
  acceptedLoadBusy: false,
}

describe('FASHN owner experiment panel (#176/#177)', () => {
  it('shows Max + v1.6 controls for owner even before realistic pieces exist', () => {
    const onProviderChange = vi.fn()
    render(
      <FashnGarmentReview
        prep={prep({ layout: 'one_piece', pieces: [
          { category: 'one-pieces', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
        ], fashn_calls: 1, estimate_cents: 8, realism_calls: 1, realism_estimate_cents: 8, combined_estimate_cents: 16 })}
        realisticPieces={null}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
        experiment={{
          ...experimentBase,
          ownerAllowed: true,
          maxSelectable: true,
          provider: 'fashn',
          onProviderChange,
        }}
      />,
    )
    expect(screen.getByTestId('fashn-max-experiment')).toBeInTheDocument()
    expect(screen.getByTestId('fashn-v16-controls')).toBeInTheDocument()
    expect(screen.getByTestId('fashn-reuse-accepted')).toBeInTheDocument()
    const maxRadio = screen
      .getByText(/FASHN Try-On Max/)
      .closest('label')!
      .querySelector('input') as HTMLInputElement
    expect(maxRadio).not.toBeDisabled()
    fireEvent.click(maxRadio)
    expect(onProviderChange).toHaveBeenCalledWith('fashn_max')
  })

  it('hides the whole Owner experiment section for non-owners (#177)', () => {
    render(
      <FashnGarmentReview
        prep={prep({ layout: 'one_piece', pieces: [
          { category: 'one-pieces', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
        ], fashn_calls: 1, estimate_cents: 8, realism_calls: 1, realism_estimate_cents: 8, combined_estimate_cents: 16 })}
        realisticPieces={null}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
        experiment={null}
      />,
    )
    expect(screen.queryByTestId('fashn-max-experiment')).not.toBeInTheDocument()
  })

  it('keeps v1.6 controls when Max is not selectable and shows unavailable status (#177)', () => {
    const onProviderChange = vi.fn()
    render(
      <FashnGarmentReview
        prep={prep({ layout: 'one_piece', pieces: [
          { category: 'one-pieces', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
        ], fashn_calls: 1, estimate_cents: 8, realism_calls: 1, realism_estimate_cents: 8, combined_estimate_cents: 16 })}
        realisticPieces={null}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
        experiment={{
          ...experimentBase,
          ownerAllowed: true,
          maxSelectable: false,
          maxUnavailableReason:
            'Try-On Max is configured but not live-armed (FASHN_TRY_ON_MAX_LIVE_HTTP).',
          provider: 'fashn',
          onProviderChange,
        }}
      />,
    )
    expect(screen.getByTestId('fashn-max-experiment')).toBeInTheDocument()
    expect(screen.getByTestId('fashn-v16-controls')).toBeInTheDocument()
    expect(screen.getByTestId('fashn-max-unavailable')).toHaveTextContent(/not live-armed/)
    const maxRadio = screen
      .getByText(/FASHN Try-On Max/)
      .closest('label')!
      .querySelector('input') as HTMLInputElement
    expect(maxRadio).toBeDisabled()
    fireEvent.click(maxRadio)
    expect(onProviderChange).not.toHaveBeenCalled()
  })

  it('shows Max Balanced/Quality + prompt when Max is selected (#177)', () => {
    render(
      <FashnGarmentReview
        prep={prep({ layout: 'one_piece', pieces: [
          { category: 'one-pieces', image_base64: TINY, bbox: [0, 0, 10, 10], opaque_pixels: 40 },
        ], fashn_calls: 1, estimate_cents: 8, realism_calls: 1, realism_estimate_cents: 8, combined_estimate_cents: 16 })}
        realisticPieces={null}
        realismBusy={false}
        realismError={null}
        detailsOpen={false}
        onToggleDetails={() => undefined}
        experiment={{
          ...experimentBase,
          ownerAllowed: true,
          maxSelectable: true,
          provider: 'fashn_max',
          onProviderChange: () => undefined,
          prompt: 'preserve garment fidelity',
          promptOpen: true,
        }}
      />,
    )
    expect(screen.getByTestId('fashn-max-controls')).toBeInTheDocument()
    expect(screen.getByText(/Balanced \(default/)).toBeInTheDocument()
    expect(screen.getByText(/Quality \(/)).toBeInTheDocument()
    expect(screen.getByTestId('fashn-max-prompt')).toHaveValue('preserve garment fidelity')
  })
})
