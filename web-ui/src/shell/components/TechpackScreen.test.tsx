import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TechpackScreen } from '@/shell/components/TechpackScreen'

const getTechpackDraft = vi.fn()
const updateTechpackDraft = vi.fn()
const exportTechpackPdf = vi.fn()
const fetchTechpackPdfBlob = vi.fn()
const fetchTechpackArtifactBlob = vi.fn()
const getTechpackAiStatus = vi.fn()
const generateTechpackAiProfessionalOneTap = vi.fn()
const getTechpackAiRun = vi.fn()
const getLatestTechpackAiRun = vi.fn()

vi.mock('@/services/techpacksApi', () => ({
  getTechpackDraft: (...args: unknown[]) => getTechpackDraft(...args),
  updateTechpackDraft: (...args: unknown[]) => updateTechpackDraft(...args),
  exportTechpackPdf: (...args: unknown[]) => exportTechpackPdf(...args),
  fetchTechpackPdfBlob: (...args: unknown[]) => fetchTechpackPdfBlob(...args),
  fetchTechpackArtifactBlob: (...args: unknown[]) => fetchTechpackArtifactBlob(...args),
  getTechpackAiStatus: (...args: unknown[]) => getTechpackAiStatus(...args),
  generateTechpackAiProfessionalOneTap: (...args: unknown[]) =>
    generateTechpackAiProfessionalOneTap(...args),
  getTechpackAiRun: (...args: unknown[]) => getTechpackAiRun(...args),
  getLatestTechpackAiRun: (...args: unknown[]) => getLatestTechpackAiRun(...args),
}))

vi.mock('@/hooks/useAuthJobImage', () => ({
  useAuthJobImage: () => ({ url: 'blob:magic-look', loading: false }),
}))

const V2_DRAFT = {
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
    schema_version: '2.0',
    workflow_stage: 'understand',
    units: 'cm',
    size_system: 'EU',
    sample_size: '',
    look_notes: '',
    designer_notes: '',
    outfit: {
      piece_count: 1,
      pieces: [
        {
          id: 'piece-1',
          category: 'dress',
          label: 'Cream Dress',
          color_hint: 'cream',
          detection_source: 'heuristic',
          materials: { shell: { name: '', composition: '', source: 'empty' } },
          closures: { type: '', source: 'empty' },
          fit: { silhouette: '' },
          finished_measurements: {
            chest_bust: { value: null, unit: 'cm', source: 'empty' },
            garment_length: { value: null, unit: 'cm', source: 'empty' },
          },
        },
      ],
      detection_confidence: 'heuristic',
      needs_user_confirm: true,
      note: 'Detection is a starting point — correct categories before generating.',
    },
    body: {
      height: { value: null, unit: 'cm', source: 'empty' },
      bust: { value: null, unit: 'cm', source: 'empty' },
      waist: { value: null, unit: 'cm', source: 'empty' },
      hip: { value: null, unit: 'cm', source: 'empty' },
      inseam: { value: null, unit: 'cm', source: 'empty' },
    },
    preferences: { fit_preference: 'regular', notes: '' },
    warnings: [],
    ai: { last_run_id: null, paid_sections: [] },
  },
  front_job_id: 'job-f',
  back_job_id: null,
  created_at: '2026-10-26T12:00:00Z',
  updated_at: '2026-10-26T12:00:00Z',
  latest_export: null,
}

describe('TechpackScreen simplified UX', () => {
  let currentDraft: typeof V2_DRAFT

  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 })
    currentDraft = structuredClone(V2_DRAFT)
    getTechpackDraft.mockReset()
    updateTechpackDraft.mockReset()
    exportTechpackPdf.mockReset()
    fetchTechpackPdfBlob.mockReset()
    fetchTechpackArtifactBlob.mockReset()
    getTechpackAiStatus.mockReset()
    generateTechpackAiProfessionalOneTap.mockReset()
    getTechpackAiRun.mockReset()
    getLatestTechpackAiRun.mockReset()
    getLatestTechpackAiRun.mockResolvedValue(null)
    getTechpackDraft.mockImplementation(async () => currentDraft)
    getTechpackAiStatus.mockResolvedValue({
      enabled: false,
      professional_available: false,
      estimate_chat_cents: 8,
      note: 'Heuristic technical generation (0 cost) always available.',
    })
    updateTechpackDraft.mockImplementation(
      async (
        _id: string,
        patch: { title?: string; style_code?: string; spec?: Record<string, unknown> },
      ) => {
        currentDraft = {
          ...currentDraft,
          title: patch.title ?? currentDraft.title,
          style_code: patch.style_code ?? currentDraft.style_code,
          spec: patch.spec
            ? ({ ...currentDraft.spec, ...patch.spec } as typeof currentDraft.spec)
            : currentDraft.spec,
        }
        return currentDraft
      },
    )
    fetchTechpackPdfBlob.mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }))
  })

  it('shows single-screen Create Real Design with Generate AI PDF', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Create Real Design' })).toBeInTheDocument()
    expect(
      screen.getByText(/Turn your Magic look into a professional AI technical pack/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Edit measurements & details/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Back to My Looks/i })).toBeInTheDocument()
    // Wizard / Basic / Save maze removed from primary flow.
    expect(screen.queryByRole('navigation', { name: /Create Real Design stages/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /Basic Technical Pack/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save Draft/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Preview PDF/i })).not.toBeInTheDocument()
  })

  it('disables Generate AI PDF when Professional unavailable', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    const gen = await screen.findByRole('button', { name: /Generate AI PDF/i })
    expect(gen).toBeDisabled()
    expect(
      screen.getByText(
        /AI Professional unavailable|provider credentials|spend ceiling|feature flag/i,
      ),
    ).toBeInTheDocument()
  })

  it('opens details editor, edits a measurement, and persists on close', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    expect(await screen.findByRole('dialog', { name: /Measurements & details/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /^Body$/i }))
    const height = await screen.findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '170' } })
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
  })

  it('keeps details open when Done flush save fails', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    updateTechpackDraft.mockRejectedValueOnce(new Error('network down'))
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    expect(await screen.findByRole('dialog', { name: /Measurements & details/i })).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('details-done'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/network down|Could not save/i)
    expect(screen.getByRole('dialog', { name: /Measurements & details/i })).toBeInTheDocument()
  })

  it('renders Magic hero with contain class (no cover crop)', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    const img = await screen.findByRole('img', { name: /Cream dress|Magic look/i })
    expect(img.className).toMatch(/heroImage/)
  })

  it('one-tap Generate shows waiting then Download PDF only when pdf_ready', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    generateTechpackAiProfessionalOneTap.mockResolvedValue({
      run_id: 'run-async',
      status: 'queued',
      cost_usd_cents: 0,
      mode: 'professional',
      accepted: true,
      progress: { phase: 'preparing', message: 'Analyzing your design…' },
    })
    getTechpackAiRun.mockResolvedValue({
      id: 'run-async',
      draft_id: 'draft-1',
      stage: 'professional',
      status: 'completed',
      cost_usd_cents: 55,
      export_id: 'exp-pro-1',
      pdf_ready: true,
      pdf_filename: 'FR-5608_r1_techpack.pdf',
      artifacts: [],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      result: {
        analysis_summary: 'ok',
        failed_sections: [],
        export_id: 'exp-pro-1',
        pdf_ready: true,
      },
    })

    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    fireEvent.click(await screen.findByRole('button', { name: /Generate AI PDF/i }))
    expect(
      await screen.findByRole('dialog', {
        name: /Creating Your AI Technical Pack|Your AI Technical Pack Is Ready/i,
      }),
    ).toBeInTheDocument()
    await waitFor(
      () => expect(getTechpackAiRun).toHaveBeenCalledWith('run-async', expect.anything()),
      { timeout: 5000 },
    )
    const dialog = await screen.findByRole('dialog', {
      name: /Your AI Technical Pack Is Ready/i,
    })
    expect(within(dialog).getByTestId('download-ai-pdf')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /View illustrations/i })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Preview PDF/i })).not.toBeInTheDocument()
  })

  it('Download PDF uses the bound Professional export id, not Basic latest_export', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    currentDraft = {
      ...V2_DRAFT,
      latest_export: {
        id: 'exp-basic-old',
        draft_id: 'draft-1',
        filename: 'basic.pdf',
        byte_size: 10,
        page_count: 1,
        revision: 1,
        status: 'DRAFT',
        verification: 'UNVERIFIED',
        metadata: { is_professional: false, generation_mode: 'none' },
        created_at: '2026-10-26T12:00:00Z',
      },
      spec: {
        ...V2_DRAFT.spec,
        ai: {
          last_run_id: 'run-pro',
          last_mode: 'professional',
          export_id: 'exp-pro-bound',
          dirty_since_generation: false,
          paid_sections: ['technical_flats'],
        },
      },
    }
    getLatestTechpackAiRun.mockResolvedValue({
      id: 'run-pro',
      draft_id: 'draft-1',
      stage: 'professional',
      status: 'completed',
      cost_usd_cents: 72,
      export_id: 'exp-pro-bound',
      pdf_ready: true,
      pdf_filename: 'FR-5608_professional.pdf',
      artifacts: [{ id: 'art-1', kind: 'flat_front' }],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      result: { export_id: 'exp-pro-bound', pdf_ready: true },
    })

    // click download in overlay
    const createEl = document.createElement.bind(document)
    const clickSpy = vi.fn()
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = createEl(tag)
      if (tag === 'a') {
        Object.defineProperty(el, 'click', { value: clickSpy })
      }
      return el
    })

    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(
      await screen.findByRole('dialog', { name: /Your AI Technical Pack Is Ready/i }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('download-ai-pdf'))
    await waitFor(() => expect(fetchTechpackPdfBlob).toHaveBeenCalledWith('exp-pro-bound'))
    expect(fetchTechpackPdfBlob).not.toHaveBeenCalledWith('exp-basic-old')
  })

  it('reuses a stable one-tap idempotency key across double-clicks', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    let resolveGen: (v: unknown) => void = () => undefined
    generateTechpackAiProfessionalOneTap.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve
        }),
    )
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const btn = await screen.findByRole('button', { name: /Generate AI PDF/i })
    fireEvent.click(btn)
    fireEvent.click(btn)
    await waitFor(() => expect(generateTechpackAiProfessionalOneTap).toHaveBeenCalledTimes(1))
    const key = generateTechpackAiProfessionalOneTap.mock.calls[0][1].idempotency_key as string
    expect(key).toMatch(/^one-tap-draft-1-r/)
    resolveGen({
      run_id: 'run-stable',
      status: 'completed',
      cost_usd_cents: 10,
      mode: 'professional',
      export_id: 'exp-1',
      pdf_ready: true,
      pdf_filename: 'ok.pdf',
      artifacts: [],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      result: { export_id: 'exp-1', pdf_ready: true },
    })
    expect(
      await screen.findByRole('dialog', { name: /Your AI Technical Pack Is Ready/i }),
    ).toBeInTheDocument()
  })

  it('maps configuration errors from one-tap generate', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    generateTechpackAiProfessionalOneTap.mockRejectedValue(
      new Error('Technical generation failed: OPENAI_REASONING_EFFORT is empty'),
    )
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByTestId('app-version')).toHaveTextContent(/App /i)
    fireEvent.click(await screen.findByRole('button', { name: /Generate AI PDF/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/server configuration problem/i)
    expect(screen.queryByText(/OPENAI_REASONING_EFFORT/i)).not.toBeInTheDocument()
  })
})
