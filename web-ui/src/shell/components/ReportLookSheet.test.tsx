import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReportLookSheet } from './ReportLookSheet'
import type { GalleryItem } from '@/services/galleryApi'

const reportGalleryItem = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  reportGalleryItem: (...args: unknown[]) => reportGalleryItem(...args),
}))

const item: GalleryItem = {
  id: 'look-1',
  design_id: null,
  look_id: 'job-1',
  user_id: 'author-1',
  title: 'Silk dress',
  image_url: null,
  visibility: 'public',
  rating_average: null,
  rating_count: 0,
  likes_count: 0,
  moderation_status: 'ok',
  created_at: '2026-11-17T00:00:00Z',
  updated_at: '2026-11-17T00:00:00Z',
  username: 'badActor',
}

describe('ReportLookSheet', () => {
  beforeEach(() => {
    reportGalleryItem.mockReset()
    reportGalleryItem.mockResolvedValue({
      id: 'rpt-1',
      gallery_item_id: item.id,
      reported_user_id: item.user_id,
      reason: 'harassment',
      status: 'open',
      created_at: '2026-11-17T00:00:00Z',
    })
  })

  it('picks a reason then requires Send with optional details', async () => {
    const onReported = vi.fn()
    const onClose = vi.fn()
    render(
      <ReportLookSheet item={item} open onClose={onClose} onReported={onReported} />,
    )

    expect(screen.getByTestId('report-look-sheet')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('report-reason-harassment'))

    expect(reportGalleryItem).not.toHaveBeenCalled()
    expect(screen.getByTestId('report-selected-reason')).toHaveTextContent(/Harassment/i)
    fireEvent.change(screen.getByTestId('report-details'), {
      target: { value: 'Cursing in the comments' },
    })
    fireEvent.click(screen.getByTestId('report-send'))

    await waitFor(() => {
      expect(reportGalleryItem).toHaveBeenCalledWith('look-1', {
        reason: 'harassment',
        details: 'Cursing in the comments',
      })
    })
    expect(onReported).toHaveBeenCalledWith('look-1')
    expect(await screen.findByText(/Thanks for reporting/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('requires details for Something else before Send', async () => {
    render(
      <ReportLookSheet item={item} open onClose={() => undefined} onReported={() => undefined} />,
    )
    fireEvent.click(screen.getByTestId('report-reason-other'))
    expect(screen.getByTestId('report-send')).toBeDisabled()
    fireEvent.change(screen.getByTestId('report-details'), {
      target: { value: 'Weird violence vibe' },
    })
    expect(screen.getByTestId('report-send')).not.toBeDisabled()
  })

  it('does not close the sheet when details focus triggers keyboard reflow click', () => {
    const onClose = vi.fn()
    render(
      <ReportLookSheet item={item} open onClose={onClose} onReported={() => undefined} />,
    )
    fireEvent.click(screen.getByTestId('report-reason-harassment'))
    const details = screen.getByTestId('report-details')
    fireEvent.focus(details)
    document.documentElement.setAttribute('data-fr-keyboard', '1')
    const scrim = details.closest('[role="presentation"]')
    expect(scrim).toBeTruthy()
    fireEvent.click(scrim!)
    expect(onClose).not.toHaveBeenCalled()
    document.documentElement.removeAttribute('data-fr-keyboard')
  })
})
