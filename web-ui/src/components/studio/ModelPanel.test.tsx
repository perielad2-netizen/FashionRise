import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ModelPanel } from '@/components/studio/ModelPanel'

describe('ModelPanel', () => {
  it('selects female and male references', () => {
    const onSelect = vi.fn()
    render(
      <ModelPanel
        selected="female"
        customPreviewUrl={null}
        onSelect={onSelect}
        onCustomFile={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Select Male reference' }))
    expect(onSelect).toHaveBeenCalledWith('male')

    fireEvent.click(screen.getByRole('button', { name: 'Select Blank reference' }))
    expect(onSelect).toHaveBeenCalledWith('blank')
  })
})
