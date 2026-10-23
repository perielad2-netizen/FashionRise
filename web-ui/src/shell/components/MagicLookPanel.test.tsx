import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MagicLookPanel } from '@/shell/components/MagicLookPanel'

describe('MagicLookPanel', () => {
  it('shows the full look image with contain sizing and keeps actions available', () => {
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
        onDownload={() => undefined}
        onRecover={() => undefined}
        onBackToSketch={() => undefined}
      />,
    )

    const img = screen.getByAltText('Magic fashion look') as HTMLImageElement
    expect(img.src).toContain('blob:look')
    expect(img.className).toMatch(/image/)

    expect(screen.getByRole('button', { name: 'Compare sketch' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Download look' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Back to sketch' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Close Magic' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Show look notes' }))
    expect(screen.getByText('A couture look')).toBeTruthy()
    expect(screen.getByText('Hat')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Compare sketch' }))
    expect(screen.getByAltText('Original sketch')).toBeTruthy()
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
})
