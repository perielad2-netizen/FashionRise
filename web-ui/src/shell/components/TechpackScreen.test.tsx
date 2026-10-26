import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TechpackScreen } from '@/shell/components/TechpackScreen'

const getTechpackDraft = vi.fn()
const updateTechpackDraft = vi.fn()
const exportTechpackPdf = vi.fn()
const fetchTechpackPdfBlob = vi.fn()
const fetchTechpackArtifactBlob = vi.fn()
const getTechpackAiStatus = vi.fn()
const confirmTechpackAi = vi.fn()
const generateTechpackAi = vi.fn()
const getTechpackAiRun = vi.fn()

vi.mock('@/services/techpacksApi', () => ({
  getTechpackDraft: (...args: unknown[]) => getTechpackDraft(...args),
  updateTechpackDraft: (...args: unknown[]) => updateTechpackDraft(...args),
  exportTechpackPdf: (...args: unknown[]) => exportTechpackPdf(...args),
  fetchTechpackPdfBlob: (...args: unknown[]) => fetchTechpackPdfBlob(...args),
  fetchTechpackArtifactBlob: (...args: unknown[]) => fetchTechpackArtifactBlob(...args),
  getTechpackAiStatus: (...args: unknown[]) => getTechpackAiStatus(...args),
  confirmTechpackAi: (...args: unknown[]) => confirmTechpackAi(...args),
  generateTechpackAi: (...args: unknown[]) => generateTechpackAi(...args),
  getTechpackAiRun: (...args: unknown[]) => getTechpackAiRun(...args),
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
    confirmTechpackAi.mockReset()
    generateTechpackAi.mockReset()
    getTechpackAiRun.mockReset()
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
    confirmTechpackAi.mockResolvedValue({
      draft_id: 'draft-1',
      stage: 'generate',
      confirm_token: 'confirm-abcdefgh',
      estimated_cost_usd_cents: 0,
      ai_enabled: false,
      mode: 'heuristic',
      message: 'Paid AI is not enabled. You can still generate a heuristic technical pack at $0.',
    })
    generateTechpackAi.mockImplementation(async () => {
      currentDraft = {
        ...currentDraft,
        spec: {
          ...currentDraft.spec,
          workflow_stage: 'generate',
          ai: {
            last_run_id: 'run-1',
            last_mode: 'heuristic',
            paid_sections: [],
            actual_cost_usd_cents: 0,
          },
        },
      }
      return {
        run_id: 'run-1',
        status: 'completed',
        cost_usd_cents: 0,
        mode: 'heuristic',
        warnings: [],
      }
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

  it('exposes Basic and disabled Professional options when AI professional is unavailable', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))

    expect(await screen.findByRole('radio', { name: /Basic Technical Pack — Free/i })).toBeInTheDocument()
    const pro = screen.getByRole('radio', { name: /AI Professional Technical Pack/i })
    expect(pro).toBeDisabled()
    expect(
      screen.getByText(/owner allowlist \/ spend ceiling not configured/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Basic PDF \/ \$0/i)).toBeInTheDocument()
    expect(screen.getByText(/Preview and Download never run paid AI/i)).toBeInTheDocument()
  })

  it('confirms Basic heuristic generate then previews PDF on generate stage', async () => {
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    expect(await screen.findByRole('radio', { name: /Basic Technical Pack — Free/i })).toHaveAttribute(
      'aria-checked',
      'true',
    )

    fireEvent.click(screen.getByRole('button', { name: /Get confirm token/i }))
    await waitFor(() =>
      expect(confirmTechpackAi).toHaveBeenCalledWith('draft-1', 'generate', 'heuristic'),
    )
    expect(await screen.findByText(/Estimated cost/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: /I confirm generating a Basic Technical Pack/i }))
    fireEvent.click(screen.getByRole('button', { name: /Generate Basic Pack/i }))
    await waitFor(() => {
      expect(generateTechpackAi).toHaveBeenCalledWith(
        'draft-1',
        expect.objectContaining({
          confirm_token: 'confirm-abcdefgh',
          mode: 'heuristic',
        }),
      )
    })

    expect(
      await screen.findByRole('button', { name: /Preview Basic PDF \(\$0 · No AI\)/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/Basic \/ No AI/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Preview and Download never run paid AI/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Preview Basic PDF \(\$0 · No AI\)/i }))
    await waitFor(() => {
      expect(updateTechpackDraft).toHaveBeenCalled()
      expect(exportTechpackPdf).toHaveBeenCalledWith('draft-1')
      expect(fetchTechpackPdfBlob).toHaveBeenCalledWith('exp-1')
    })
    expect(await screen.findByTitle('Tech pack PDF preview')).toBeInTheDocument()
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

  it('runs Professional confirm + generate with cost line and artifact thumbs when available', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      estimate_professional_cents_min: 40,
      estimate_professional_cents_max: 120,
      max_usd_per_run: 2,
      vision_model: 'gpt-4.1-mini',
      image_model: 'gpt-image-1',
      note: 'Professional available',
    })
    confirmTechpackAi.mockResolvedValue({
      draft_id: 'draft-1',
      stage: 'generate',
      confirm_token: 'pro-confirm-token',
      estimated_cost_usd_cents: 85,
      ai_enabled: true,
      max_usd_per_run: 2,
      mode: 'professional',
      message: 'Professional estimate ready',
    })
    generateTechpackAi.mockImplementation(async () => {
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
      }
    })

    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))

    const pro = await screen.findByRole('radio', { name: /AI Professional Technical Pack/i })
    expect(pro).not.toBeDisabled()
    fireEvent.click(pro)
    expect(pro).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText(/Status estimate/i)).toBeInTheDocument()
    expect(
      screen.getByRole('checkbox', { name: /Propose unverified back view/i }),
    ).not.toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: /Get cost estimate/i }))
    await waitFor(() =>
      expect(confirmTechpackAi).toHaveBeenCalledWith('draft-1', 'generate', 'professional'),
    )
    expect(screen.getAllByText(/Estimated cost/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Max allowance/i)).toBeInTheDocument()

    fireEvent.click(
      screen.getByRole('checkbox', { name: /I confirm generating an AI Professional Technical Pack/i }),
    )
    fireEvent.click(screen.getByRole('button', { name: /Generate Professional Pack/i }))
    await waitFor(() => {
      expect(generateTechpackAi).toHaveBeenCalledWith(
        'draft-1',
        expect.objectContaining({
          confirm_token: 'pro-confirm-token',
          mode: 'professional',
          propose_back: false,
        }),
      )
    })
    await waitFor(() => expect(fetchTechpackArtifactBlob).toHaveBeenCalledWith('art-1'))
    expect(await screen.findByAltText(/flat_front technical illustration/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Export Professional PDF/i })).toBeInTheDocument()
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

  it('shows build version and maps configuration errors near AI controls', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      estimate_professional_cents_min: 40,
      estimate_professional_cents_max: 120,
      max_usd_per_run: 8,
      note: 'Professional available',
    })
    confirmTechpackAi.mockRejectedValue(
      new Error('Technical generation failed: OPENAI_REASONING_EFFORT is empty'),
    )
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    expect(await screen.findByText(/Build /i)).toBeInTheDocument()
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    const pro = await screen.findByRole('radio', { name: /AI Professional Technical Pack/i })
    fireEvent.click(pro)
    fireEvent.click(screen.getByRole('button', { name: /Get cost estimate/i }))
    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(/server configuration problem/i)
    expect(screen.getByText(/No chargeable AI work ran/i)).toBeInTheDocument()
    expect(screen.queryByText(/OPENAI_REASONING_EFFORT/i)).not.toBeInTheDocument()
  })

  it('reuses a stable intent idempotency key for Professional generate', async () => {
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      owner_allowlisted: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    confirmTechpackAi.mockResolvedValue({
      draft_id: 'draft-1',
      stage: 'generate',
      confirm_token: 'stable-confirm-token',
      estimated_cost_usd_cents: 50,
      ai_enabled: true,
      max_usd_per_run: 8,
      mode: 'professional',
      message: 'ready',
    })
    render(<TechpackScreen draftId="draft-1" onBack={() => undefined} />)
    await screen.findByText('Create Real Design')
    const stepper = screen.getByRole('navigation', { name: /Create Real Design stages/i })
    fireEvent.click(within(stepper).getByRole('button', { name: /Generate Technical Design/i }))
    fireEvent.click(await screen.findByRole('radio', { name: /AI Professional Technical Pack/i }))
    fireEvent.click(screen.getByRole('button', { name: /Get cost estimate/i }))
    await waitFor(() => expect(confirmTechpackAi).toHaveBeenCalled())
    fireEvent.click(
      screen.getByRole('checkbox', { name: /I confirm generating an AI Professional Technical Pack/i }),
    )
    fireEvent.click(screen.getByRole('button', { name: /Generate Professional Pack/i }))
    await waitFor(() => {
      expect(generateTechpackAi).toHaveBeenCalledWith(
        'draft-1',
        expect.objectContaining({
          idempotency_key: 'intent-draft-1-stable-confirm-token',
          mode: 'professional',
        }),
      )
    })
  })

  it('opens Step 4 AI controls in a modal on mobile', async () => {
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
    expect(screen.getByRole('radio', { name: /Basic Technical Pack — Free/i })).toBeInTheDocument()
    expect(
      screen.getByRole('radio', { name: /AI Professional Technical Pack/i }),
    ).toBeInTheDocument()
  })
})
