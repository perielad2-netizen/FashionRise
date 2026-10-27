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
  useAuthJobImage: () => ({ url: null, loading: false }),
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

describe('TechpackScreen', () => {
  let currentDraft: typeof V2_DRAFT

  beforeEach(() => {
    // Reset viewport mocks so desktop tests are not polluted by mobile cases.
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
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1280 })
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
    generateTechpackAiProfessionalOneTap.mockResolvedValue({
      run_id: 'run-1',
      status: 'completed',
      cost_usd_cents: 72,
      mode: 'professional',
      artifacts: [],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
    })
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
    fetchTechpackArtifactBlob.mockResolvedValue(
      new Blob(['png'], { type: 'image/png' }),
    )
  })

  it('loads draft and shows DRAFT/UNVERIFIED banner with stage 1', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Create Real Design' })).toBeInTheDocument()
    expect(screen.getByText(/Patternmaker review required/i)).toBeInTheDocument()
    expect(screen.getAllByText(/not guaranteed/i).length).toBeGreaterThan(0)
    expect(screen.getByDisplayValue('Cream dress')).toBeInTheDocument()
    expect(screen.getByDisplayValue('FR-5608')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Understand My Design/i })).toBeInTheDocument()
    expect(screen.getByDisplayValue('Cream Dress')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /Create Real Design stages/i })).toBeInTheDocument()
  })

  it('moves through customize stage with garment tabs and FieldHelp', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Customize Each Piece/i }))
    expect(await screen.findByRole('heading', { name: /Customize Each Piece/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Outfit Overview/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /DRESS — CREAM DRESS/i }))
    expect(screen.getByRole('textbox', { name: /Shell fabric/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Help: Shell fabric/i }))
    expect(await screen.findByRole('dialog', { name: /Shell fabric/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^cotton$/i }))
    expect(screen.getByRole('textbox', { name: /Shell fabric/i })).toHaveValue('cotton')
  })

  it('shows garment-specific finished measurements without inventing trouser POMs on a dress', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Measurements/i }))
    expect(await screen.findByRole('heading', { name: /Measurements and Preferences/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /DRESS — CREAM DRESS/i }))
    expect(screen.getByText(/Chest \/ bust/i)).toBeInTheDocument()
    expect(screen.getByText(/Garment length/i)).toBeInTheDocument()
    expect(screen.queryByText(/^Inseam$/i)).not.toBeInTheDocument()
  })


  it('shows one Generate AI PDF button and disables it when Professional unavailable', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))

    expect(screen.queryByRole('radio', { name: /Basic Technical Pack/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Get cost estimate/i })).not.toBeInTheDocument()
    const gen = await screen.findByRole('button', { name: /Generate AI PDF/i })
    expect(gen).toBeDisabled()
    expect(
      screen.getByText(
        /AI Professional unavailable|provider credentials|spend ceiling|feature flag/i,
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/Preview and Download never run paid AI/i)).toBeInTheDocument()
  })

  it('one-tap Generate AI PDF opens progress overlay and loads illustrations', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      estimate_professional_cents_min: 40,
      estimate_professional_cents_max: 120,
      max_usd_per_run: 2,
      vision_model: 'gpt-6-luna',
      image_model: 'gpt-image-2.5-sunburst',
      note: 'Professional available',
    })
    generateTechpackAiProfessionalOneTap.mockImplementation(async () => {
      currentDraft = {
        ...currentDraft,
        spec: {
          ...currentDraft.spec,
          workflow_stage: 'generate',
          ai: { last_run_id: 'run-pro', last_mode: 'professional', paid_sections: ['flat_front'] },
        },
      }
      return {
        run_id: 'run-pro',
        status: 'completed',
        cost_usd_cents: 72,
        mode: 'professional',
        artifacts: [
          {
            id: 'art-1',
            piece_id: 'piece-1',
            kind: 'flat_front',
            url_path: '/techpacks/artifacts/art-1/image',
            review_state: 'unverified',
          },
        ],
        estimated_cost_usd_cents: 85,
        actual_cost_usd_cents: 72,
        analysis_summary: 'Dress front flat generated',
        progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      }
    })

    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))

    const gen = await screen.findByRole('button', { name: /Generate AI PDF/i })
    expect(gen).not.toBeDisabled()
    expect(screen.queryByRole('checkbox', { name: /I confirm/i })).not.toBeInTheDocument()
    fireEvent.click(gen)
    expect(await screen.findByRole('dialog', { name: /Creating your AI Technical Pack|Your AI Technical Design is Ready/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(generateTechpackAiProfessionalOneTap).toHaveBeenCalledWith(
        'draft-1',
        expect.objectContaining({
          idempotency_key: expect.stringMatching(/^one-tap-draft-1-/),
          propose_back: true,
        }),
      )
    })
    await waitFor(() => expect(fetchTechpackArtifactBlob).toHaveBeenCalledWith('art-1'))
    expect(await screen.findByText(/Your AI Technical Design is Ready/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View illustrations/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Preview PDF/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
  })

  it('opens a full-screen modal form when a step is tapped on mobile', async () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: String(query).includes('max-width: 720px'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 390 })
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    expect(screen.getByText(/Tap a step to open its form/i)).toBeInTheDocument()
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Understand My Design/i }))
    expect(await screen.findByRole('dialog', { name: /Understand My Design/i })).toBeInTheDocument()
    expect(screen.getByText(/Step 1 of 4/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Cream dress')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save & next step/i })).toBeInTheDocument()
  })

  it('opens mobile measurements sheet at Android-sized viewports', async () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: String(query).includes('max-width: 720px'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 390 })
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Measurements/i }))
    expect(await screen.findByRole('dialog', { name: /Body measurements/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save & Done/i })).toBeInTheDocument()
  })

  it('wraps a V1 draft locally and shows migration notice', async () => {
    currentDraft = {
      ...V2_DRAFT,
      spec: {
        schema_version: '1.0',
        body: { height: { value: null, unit: 'cm', source: 'empty' } },
        garment: { garment_length: { value: null, unit: 'cm', source: 'estimate' } },
        materials: { shell: { name: 'Silk', composition: '' } },
        closures: { type: '' },
        fit: { silhouette: '' },
        designer_notes: '',
      } as unknown as typeof V2_DRAFT.spec,
    }
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByText(/older format/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Silk')).toBeInTheDocument()
  })

  it('keeps DRAFT/UNVERIFIED visible in the header pill', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const pills = screen.getAllByText(/DRAFT\s*\/\s*UNVERIFIED/)
    expect(pills.length).toBeGreaterThan(0)
  })

  it('maps configuration errors from one-tap generate', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      estimate_professional_cents_min: 40,
      estimate_professional_cents_max: 120,
      max_usd_per_run: 8,
      note: 'Professional available',
    })
    generateTechpackAiProfessionalOneTap.mockRejectedValue(
      new Error('Technical generation failed: OPENAI_REASONING_EFFORT is empty'),
    )
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByTestId('app-version')).toHaveTextContent(/App /i)
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Generate AI PDF/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/server configuration problem/i)
    expect(screen.queryByText(/OPENAI_REASONING_EFFORT/i)).not.toBeInTheDocument()
  })

  it('reuses a stable one-tap idempotency key across double-clicks', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
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
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    const btn = await screen.findByRole('button', { name: /Generate AI PDF/i })
    fireEvent.click(btn)
    fireEvent.click(btn)
    await waitFor(() => expect(generateTechpackAiProfessionalOneTap).toHaveBeenCalledTimes(1))
    const key = generateTechpackAiProfessionalOneTap.mock.calls[0][1].idempotency_key as string
    expect(key).toMatch(/^one-tap-draft-1-/)
    resolveGen({
      run_id: 'run-stable',
      status: 'completed',
      cost_usd_cents: 10,
      mode: 'professional',
      artifacts: [],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
    })
    expect(await screen.findByText(/Your AI Technical Design is Ready/i)).toBeInTheDocument()
  })

  it('opens Step 4 Generate AI PDF controls in a modal on mobile', async () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: String(query).includes('max-width: 720px'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 390 })
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    expect(
      await screen.findByRole('dialog', { name: /Generate Technical Design/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
    // Done footer removed on Step 4 — Generate AI PDF is the only primary action.
    expect(screen.queryByRole('button', { name: /^Done$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /Basic Technical Pack/i })).not.toBeInTheDocument()
  })

  it('202 queued generate polls status and shows ready without Done', async () => {
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
      progress: { phase: 'preparing', message: 'Preparing your design' },
    })
    getTechpackAiRun.mockResolvedValue({
      id: 'run-async',
      draft_id: 'draft-1',
      stage: 'professional',
      status: 'completed',
      cost_usd_cents: 55,
      artifacts: [
        {
          id: 'art-async',
          piece_id: 'piece-1',
          kind: 'flat_front',
          url_path: '/techpacks/artifacts/art-async/image',
        },
      ],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      result: { analysis_summary: 'ok', failed_sections: [] },
    })

    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Generate AI PDF/i }))
    expect(
      await screen.findByRole('dialog', {
        name: /Creating your AI Technical Pack|Your AI Technical Design is Ready/i,
      }),
    ).toBeInTheDocument()
    await waitFor(
      () => expect(getTechpackAiRun).toHaveBeenCalledWith('run-async', expect.anything()),
      { timeout: 5000 },
    )
    expect(await screen.findByText(/Your AI Technical Design is Ready/i)).toBeInTheDocument()
  })

})
