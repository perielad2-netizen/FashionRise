import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TechpackScreen } from '@/shell/components/TechpackScreen'

const getTechpackDraft = vi.fn()
const updateTechpackDraft = vi.fn()
const exportTechpackPdf = vi.fn()
const fetchTechpackPdfBlob = vi.fn()

vi.mock('@/services/techpacksApi', () => ({
  getTechpackDraft: (...args: unknown[]) => getTechpackDraft(...args),
  updateTechpackDraft: (...args: unknown[]) => updateTechpackDraft(...args),
  exportTechpackPdf: (...args: unknown[]) => exportTechpackPdf(...args),
  fetchTechpackPdfBlob: (...args: unknown[]) => fetchTechpackPdfBlob(...args),
}))

vi.mock('@/hooks/useAuthJobImage', () => ({
  useAuthJobImage: () => ({ url: null, loading: false }),
}))

const DRAFT = {
  id: 'draft-1',
  user_id: 'u1',
  look_id: 'look-1',
  design_id: null,
  title: 'Cream dress',
  style_code: 'FR-5608',
  revision: 1,
  status: 'DRAFT',
  verification: 'UNVERIFIED',
  spec: {
    body: { height: { value: null, unit: 'cm', source: 'empty' } },
    garment: { garment_length: { value: null, unit: 'cm', source: 'estimate' } },
    materials: { shell: { name: '', composition: '' } },
    closures: { type: '' },
    fit: { silhouette: '' },
    designer_notes: '',
  },
  front_job_id: 'job-f',
  back_job_id: null,
  created_at: '2026-10-26T12:00:00Z',
  updated_at: '2026-10-26T12:00:00Z',
  latest_export: null,
}

describe('TechpackScreen', () => {
  beforeEach(() => {
    getTechpackDraft.mockReset()
    updateTechpackDraft.mockReset()
    exportTechpackPdf.mockReset()
    fetchTechpackPdfBlob.mockReset()
    getTechpackDraft.mockResolvedValue(DRAFT)
    updateTechpackDraft.mockImplementation(async (_id: string, patch: { title?: string }) => ({
      ...DRAFT,
      title: patch.title ?? DRAFT.title,
      latest_export: null,
    }))
    exportTechpackPdf.mockResolvedValue({
      id: 'exp-1',
      draft_id: 'draft-1',
      filename: 'FR-5608_r1_techpack.pdf',
      byte_size: 1200,
      page_count: 5,
      revision: 1,
      status: 'DRAFT',
      verification: 'UNVERIFIED',
      metadata: {},
      created_at: '2026-10-26T12:05:00Z',
    })
    fetchTechpackPdfBlob.mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }))
  })

  it('loads draft and shows DRAFT/UNVERIFIED banner', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Create Real Design' })).toBeInTheDocument()
    expect(screen.getByText(/Patternmaker review required/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Cream dress')).toBeInTheDocument()
    expect(screen.getByDisplayValue('FR-5608')).toBeInTheDocument()
  })

  it('saves then previews PDF', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    fireEvent.click(screen.getByRole('button', { name: /Preview PDF/i }))
    await waitFor(() => {
      expect(updateTechpackDraft).toHaveBeenCalled()
      expect(exportTechpackPdf).toHaveBeenCalledWith('draft-1')
      expect(fetchTechpackPdfBlob).toHaveBeenCalledWith('exp-1')
    })
    expect(await screen.findByTitle('Tech pack PDF preview')).toBeInTheDocument()
  })
})
