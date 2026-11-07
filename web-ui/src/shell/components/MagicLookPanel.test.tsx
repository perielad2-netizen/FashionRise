import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MagicLookPanel } from '@/shell/components/MagicLookPanel'

describe('MagicLookPanel', () => {
  it('shows the full look image with contain sizing and keeps final look download', () => {
    const onDownload = vi.fn()
    render(
      <MagicLookPanel
        open
        phase="ready"
        result={{
          jobId: 'job-1',
          status: 'completed',
          summary: 'A couture look',
          bullets: ['Hat', 'Shoes'],
          hasImage: true,
        }}
        lookObjectUrl="blob:look"
        sketchObjectUrl="blob:sketch"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={onDownload}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )

    const img = screen.getByAltText('Magic fashion look') as HTMLImageElement
    expect(img.src).toContain('blob:look')
    expect(img.className).toMatch(/image/)

    expect(screen.getByRole('button', { name: 'Compare sketch' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Download look' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'View in My Looks' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Back to sketch' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Close Magic' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Download look' }))
    expect(onDownload).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Show look notes' }))
    expect(screen.getByText('A couture look')).toBeTruthy()
    expect(screen.getByText('Hat')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Compare sketch' }))
    expect(screen.getByAltText('Original sketch')).toBeTruthy()
  })

  it('labels Try On Person results without changing Fashion Magic copy', () => {
    render(
      <MagicLookPanel
        open
        phase="ready"
        resultMode="try_on"
        result={{
          jobId: 'job-try',
          status: 'completed',
          summary: 'Try On Person preview ready',
          bullets: ['Original photo preserved'],
          hasImage: true,
        }}
        lookObjectUrl="blob:tryon"
        sketchObjectUrl="blob:garment"
        originalPhotoUrl="blob:photo"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
        onViewInMyLooks={() => undefined}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Try On Person' })).toBeTruthy()
    expect(screen.getByAltText('Try On Person preview')).toBeTruthy()
    expect(screen.queryByText('Not a faithful try-on')).toBeNull()
    expect(screen.getByRole('button', { name: 'Compare original' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Download preview' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save in My Looks' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Compare original' }))
    expect(screen.getByAltText('Original model photo')).toBeTruthy()
    expect(screen.getByLabelText('Original versus try-on')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Show original only' }))
    expect(screen.getByAltText('Original model photo')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Compare garment' }))
    expect(screen.getByAltText('Garment artwork')).toBeTruthy()
  })

  it('shows a visible fidelity banner and hides Save in My Looks for rejected try-ons', () => {
    render(
      <MagicLookPanel
        open
        phase="ready"
        resultMode="try_on"
        result={{
          jobId: 'job-bad',
          status: 'completed_unverified',
          summary: 'Separate trouser legs are missing or merged.',
          bullets: ['Not production-ready'],
          hasImage: true,
          fidelityOk: false,
          structureReviewState: 'failed',
          structureReviewMessage: 'Separate trouser legs are missing or merged.',
          structureRejected: true,
        }}
        lookObjectUrl="blob:tryon-bad"
        sketchObjectUrl="blob:garment"
        originalPhotoUrl="blob:photo"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
        onViewInMyLooks={() => undefined}
      />,
    )
    expect(screen.getByText('Not a faithful try-on')).toBeTruthy()
    expect(screen.getByText(/Separate trouser legs are missing or merged/i)).toBeTruthy()
    expect(screen.getByAltText(/structural mismatch flagged/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Save in My Looks' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Download preview' })).toBeTruthy()
  })

  it('keeps dual Front/Back Magic look downloads', () => {
    const onDownloadSide = vi.fn()
    const onViewSide = vi.fn()
    render(
      <MagicLookPanel
        open
        phase="ready"
        result={null}
        lookObjectUrl={null}
        sketchObjectUrl={null}
        error={null}
        canRecover={false}
        dual={{
          operationId: 'op-1',
          viewSide: 'front',
          onViewSide,
          front: {
            phase: 'ready',
            result: {
              jobId: 'jf',
              status: 'completed',
              summary: 'Front look',
              bullets: [],
              hasImage: true,
            },
            lookObjectUrl: 'blob:front',
            sketchObjectUrl: 'blob:sk-front',
            error: null,
            canRetry: false,
          },
          back: {
            phase: 'ready',
            result: {
              jobId: 'jb',
              status: 'completed',
              summary: 'Back look',
              bullets: [],
              hasImage: true,
            },
            lookObjectUrl: 'blob:back',
            sketchObjectUrl: 'blob:sk-back',
            error: null,
            canRetry: false,
          },
          onRetrySide: () => undefined,
          onDownloadSide,
        }}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )
    expect(screen.getByAltText('Magic fashion look (front)')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Download front' }))
    expect(onDownloadSide).toHaveBeenCalledWith('front')
    fireEvent.click(screen.getByRole('tab', { name: /Back/i }))
    expect(onViewSide).toHaveBeenCalledWith('back')
  })

  it('offers View in My Looks when ready and a handler is provided', () => {
    const onViewInMyLooks = vi.fn()
    render(
      <MagicLookPanel
        open
        phase="ready"
        result={{
          jobId: 'job-1',
          status: 'completed',
          summary: 'A couture look',
          bullets: [],
          hasImage: true,
        }}
        lookObjectUrl="blob:look"
        sketchObjectUrl="blob:sketch"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
        onViewInMyLooks={onViewInMyLooks}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'View in My Looks' }))
    expect(onViewInMyLooks).toHaveBeenCalledTimes(1)
  })

  it('does not render when closed', () => {
    const { container } = render(
      <MagicLookPanel
        open={false}
        phase="idle"
        result={null}
        lookObjectUrl={null}
        sketchObjectUrl={null}
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows generic try-on spinner copy and strips provider/cost hints (#178)', () => {
    render(
      <MagicLookPanel
        open
        phase="polling"
        resultMode="try_on"
        result={null}
        lookObjectUrl={null}
        sketchObjectUrl={null}
        statusHint="Running FASHN Max — 2 credits"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )
    expect(screen.getByText('Generating your try-on preview...')).toBeTruthy()
    expect(screen.queryByText(/FASHN/i)).toBeNull()
    expect(screen.queryByText(/credit/i)).toBeNull()
    // Busy/start: no Stop waiting / Back to sketch — Close dismisses only.
    expect(screen.queryByRole('button', { name: 'Stop waiting' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Back to sketch' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cancel wait' })).toBeNull()
  })

  it('hides Stop waiting and Back to sketch while Fashion Magic is creating', () => {
    render(
      <MagicLookPanel
        open
        phase="polling"
        result={null}
        lookObjectUrl={null}
        sketchObjectUrl={null}
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )
    expect(screen.getByText('Creating your look…')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Stop waiting' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Back to sketch' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Close Magic' })).toBeTruthy()
  })

  it('hides experiment metadata on normal smart try-on results (#179)', () => {
    render(
      <MagicLookPanel
        open
        phase="ready"
        resultMode="try_on"
        result={{
          jobId: 'job-smart',
          status: 'completed',
          summary: 'Try On Person preview ready',
          bullets: [],
          hasImage: true,
          // Smart public Max must not populate experimentMeta / verdicts.
          experimentMeta: null,
        }}
        lookObjectUrl="blob:smart"
        sketchObjectUrl="blob:garment"
        error={null}
        canRecover={false}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
        onViewInMyLooks={() => undefined}
      />,
    )
    expect(screen.queryByTestId('try-on-experiment-meta')).toBeNull()
    expect(screen.queryByText(/Accepted/i)).toBeNull()
    expect(screen.queryByText(/Experiment ·/i)).toBeNull()
    expect(screen.getByRole('button', { name: 'Save in My Looks' })).toBeTruthy()
  })

  it('keeps owner experiment verdict controls when experiment provenance is true (#179)', () => {
    const onVerdict = vi.fn()
    render(
      <MagicLookPanel
        open
        phase="ready"
        resultMode="try_on"
        result={{
          jobId: 'job-exp',
          status: 'completed',
          summary: 'experiment',
          bullets: [],
          hasImage: true,
          experimentMeta: {
            experiment: true,
            verdict: 'unreviewed',
            provider: 'fashn_tryon_max',
            promptVersion: 'max-v1',
            costCents: 12,
            predictionIds: ['pred-12345678'],
            garmentRealismJobId: null,
            approvedGarmentShas: ['abc123456789'],
            croquisId: 'croq-1',
            croquisVersion: 1,
            v16Settings: null,
            fashnMaxExperiment: { generation_mode: 'quality', resolution: '1k', seed: 1 },
          },
        }}
        lookObjectUrl="blob:exp"
        sketchObjectUrl="blob:garment"
        error={null}
        canRecover={false}
        experimentVerdictBusy={false}
        onExperimentVerdict={onVerdict}
        onClose={() => undefined}
        onCancel={() => undefined}
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )
    expect(screen.getByTestId('try-on-experiment-meta')).toBeTruthy()
    expect(screen.getByTestId('try-on-experiment-verdict')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Accepted' })).toBeTruthy()
    // Experiment results block Save in My Looks.
    expect(screen.queryByRole('button', { name: 'Save in My Looks' })).toBeNull()
  })
})
