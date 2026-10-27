/**
 * PDF validity after quiet autosave: designer edits must never leave Download PDF
 * pointing at an outdated Professional pack, and syncing server ai metadata must
 * not re-arm the autosave loop.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TechpackScreen } from '@/shell/components/TechpackScreen'

const getTechpackDraft = vi.fn()
const updateTechpackDraft = vi.fn()
const getTechpackAiStatus = vi.fn()
const getLatestTechpackAiRun = vi.fn()
const generateTechpackAiProfessionalOneTap = vi.fn()
const getTechpackAiRun = vi.fn()
const fetchTechpackPdfBlob = vi.fn()
const exportTechpackPdf = vi.fn()
const fetchTechpackArtifactBlob = vi.fn()

vi.mock('@/services/techpacksApi', () => ({
  getTechpackDraft: (...args: unknown[]) => getTechpackDraft(...args),
  updateTechpackDraft: (...args: unknown[]) => updateTechpackDraft(...args),
  getTechpackAiStatus: (...args: unknown[]) => getTechpackAiStatus(...args),
  getLatestTechpackAiRun: (...args: unknown[]) => getLatestTechpackAiRun(...args),
  generateTechpackAiProfessionalOneTap: (...args: unknown[]) =>
    generateTechpackAiProfessionalOneTap(...args),
  getTechpackAiRun: (...args: unknown[]) => getTechpackAiRun(...args),
  fetchTechpackPdfBlob: (...args: unknown[]) => fetchTechpackPdfBlob(...args),
  exportTechpackPdf: (...args: unknown[]) => exportTechpackPdf(...args),
  fetchTechpackArtifactBlob: (...args: unknown[]) => fetchTechpackArtifactBlob(...args),
}))

vi.mock('@/hooks/useAuthJobImage', () => ({
  useAuthJobImage: () => ({ url: 'blob:magic-look', loading: false }),
}))

type Draft = {
  id: string
  user_id: string
  look_id: string
  design_id: null
  title: string
  style_code: string
  revision: number
  status: string
  verification: string
  spec: Record<string, unknown>
  front_job_id: string
  back_job_id: null
  created_at: string
  updated_at: string
  latest_export: {
    id: string
    draft_id: string
    filename: string
    byte_size: number
    page_count: number
    revision: number
    status: string
    verification: string
    metadata: Record<string, unknown>
    created_at: string
  } | null
}

function professionalDraft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: 'draft-pdf',
    user_id: 'u1',
    look_id: 'look-1',
    design_id: null,
    title: 'Lavender hoodie set',
    style_code: 'FR-LAVN',
    revision: 5,
    status: 'DRAFT',
    verification: 'UNVERIFIED',
    spec: {
      schema_version: '2.0',
      workflow_stage: 'generate',
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
            category: 'hoodie',
            label: 'Lavender Hoodie',
            materials: { shell: { name: 'terry', source: 'ai_inferred' } },
            closures: { type: '', source: 'empty' },
            fit: { silhouette: '' },
            finished_measurements: {
              chest_bust: { value: null, unit: 'cm', source: 'empty' },
            },
          },
        ],
      },
      body: {
        height: { value: null, unit: 'cm', source: 'empty' },
        waist: { value: null, unit: 'cm', source: 'empty' },
      },
      preferences: { fit_preference: 'regular', notes: '' },
      warnings: [],
      ai: {
        last_run_id: 'run-pro-1',
        last_mode: 'professional',
        export_id: 'exp-pro-1',
        dirty_since_generation: false,
        paid_sections: ['professional'],
      },
    },
    front_job_id: 'job-f',
    back_job_id: null,
    created_at: '2026-10-27T12:00:00Z',
    updated_at: '2026-10-27T12:00:00Z',
    latest_export: {
      id: 'exp-pro-1',
      draft_id: 'draft-pdf',
      filename: 'FR-LAVN_r5_techpack.pdf',
      byte_size: 1000,
      page_count: 4,
      revision: 5,
      status: 'READY',
      verification: 'UNVERIFIED',
      metadata: { is_professional: true },
      created_at: '2026-10-27T12:00:00Z',
    },
    ...overrides,
  }
}

function stubMatchMedia(width: number) {
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
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width })
}

describe.each([
  ['mobile', 390],
  ['tablet', 768],
  ['desktop', 1366],
] as const)('TechpackScreen PDF validity (%s %dpx)', (_label, width) => {
  let currentDraft: Draft

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubMatchMedia(width)
    currentDraft = professionalDraft()
    getTechpackDraft.mockReset()
    updateTechpackDraft.mockReset()
    getTechpackAiStatus.mockReset()
    getLatestTechpackAiRun.mockReset()
    generateTechpackAiProfessionalOneTap.mockReset()
    getTechpackAiRun.mockReset()
    fetchTechpackPdfBlob.mockReset()
    getLatestTechpackAiRun.mockResolvedValue(null)
    getTechpackDraft.mockImplementation(async () => structuredClone(currentDraft))
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      const priorAi =
        currentDraft.spec.ai && typeof currentDraft.spec.ai === 'object'
          ? (currentDraft.spec.ai as Record<string, unknown>)
          : {}
      const nextSpec = patch.spec
        ? ({ ...currentDraft.spec, ...(patch.spec as object) } as Record<string, unknown>)
        : currentDraft.spec
      const mergedAi = {
        ...priorAi,
        ...((nextSpec.ai as Record<string, unknown> | undefined) ?? {}),
        last_run_id: priorAi.last_run_id,
        last_mode: priorAi.last_mode,
        export_id: priorAi.export_id,
        dirty_since_generation: true,
      }
      currentDraft = {
        ...currentDraft,
        revision: currentDraft.revision + 1,
        title: (patch.title as string) ?? currentDraft.title,
        style_code: (patch.style_code as string) ?? currentDraft.style_code,
        spec: { ...nextSpec, ai: mergedAi },
        updated_at: new Date().toISOString(),
      }
      return structuredClone(currentDraft)
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('valid Professional PDF draft idle → Download PDF and 0 PATCH', async () => {
    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    expect(await screen.findByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Generate AI PDF/i })).not.toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
  })

  it('local edit immediately switches away from Download PDF before PATCH', async () => {
    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    await screen.findByRole('button', { name: /Download PDF/i })
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    const dialog = await screen.findByRole('dialog', { name: /Measurements & details/i })
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '170' } })
    // Before debounce fires — local dirty must already invalidate Download.
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
    expect(screen.queryByRole('button', { name: /Download PDF/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
  })

  it('PATCH dirty_since_generation=true keeps Generate; syncing ai does not PATCH again', async () => {
    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    await screen.findByRole('button', { name: /Download PDF/i })
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    const dialog = await screen.findByRole('dialog', { name: /Measurements & details/i })
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    fireEvent.change(await within(dialog).findByLabelText(/^Height$/i), {
      target: { value: '172' },
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(1))
    expect(
      (currentDraft.spec.ai as { dirty_since_generation?: boolean }).dirty_since_generation,
    ).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    // Syncing server ai metadata must not re-arm autosave.
    expect(updateTechpackDraft).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download PDF/i })).not.toBeInTheDocument()
    expect(
      screen.getByText(/Details changed since your last AI Technical Pack/i),
    ).toBeInTheDocument()
  })

  it('edit during in-flight PATCH retains newer value and Done flushes it', async () => {
    let release!: (value: Draft) => void
    const gate = new Promise<Draft>((resolve) => {
      release = resolve
    })
    let calls = 0
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      calls += 1
      const priorAi =
        currentDraft.spec.ai && typeof currentDraft.spec.ai === 'object'
          ? (currentDraft.spec.ai as Record<string, unknown>)
          : {}
      const nextSpec = patch.spec
        ? ({ ...currentDraft.spec, ...(patch.spec as object) } as Record<string, unknown>)
        : currentDraft.spec
      const built: Draft = {
        ...currentDraft,
        revision: currentDraft.revision + calls,
        title: (patch.title as string) ?? currentDraft.title,
        style_code: (patch.style_code as string) ?? currentDraft.style_code,
        spec: {
          ...nextSpec,
          ai: {
            ...priorAi,
            ...((nextSpec.ai as object) ?? {}),
            dirty_since_generation: true,
            last_run_id: priorAi.last_run_id,
            last_mode: priorAi.last_mode,
            export_id: priorAi.export_id,
          },
        },
        updated_at: new Date().toISOString(),
      }
      if (calls === 1) {
        await gate
        currentDraft = built
        return structuredClone(built)
      }
      currentDraft = built
      return structuredClone(built)
    })

    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    await screen.findByRole('button', { name: /Download PDF/i })
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    const dialog = await screen.findByRole('dialog', { name: /Measurements & details/i })
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '160' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    await waitFor(() => expect(calls).toBe(1))

    // Newer edit while first PATCH is in flight.
    fireEvent.change(height, { target: { value: '165' } })
    release(currentDraft)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(800)
    })
    await waitFor(() => expect(updateTechpackDraft.mock.calls.length).toBeGreaterThanOrEqual(2))

    const lastPatch = updateTechpackDraft.mock.calls.at(-1)?.[1] as {
      spec: { body: { height: { value: number | string | null } } }
    }
    expect(String(lastPatch.spec.body.height.value)).toBe('165')

    // Done must not discard while clean after flush.
    fireEvent.change(height, { target: { value: '166' } })
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    const donePatch = updateTechpackDraft.mock.calls.at(-1)?.[1] as {
      spec: { body: { height: { value: number | string | null } } }
    }
    expect(String(donePatch.spec.body.height.value)).toBe('166')
  })

  it('reload of already-outdated draft keeps Generate AI PDF', async () => {
    currentDraft = professionalDraft({
      spec: {
        ...professionalDraft().spec,
        ai: {
          last_run_id: 'run-pro-1',
          last_mode: 'professional',
          export_id: 'exp-pro-1',
          dirty_since_generation: true,
          paid_sections: ['professional'],
        },
      },
    })
    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    expect(await screen.findByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download PDF/i })).not.toBeInTheDocument()
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
  })

  it('completed Professional run restores Download PDF for the new export', async () => {
    currentDraft = professionalDraft({
      spec: {
        ...professionalDraft().spec,
        ai: {
          last_run_id: 'run-pro-1',
          last_mode: 'professional',
          export_id: 'exp-pro-1',
          dirty_since_generation: true,
          paid_sections: ['professional'],
        },
      },
    })
    let generationStarted = false
    generateTechpackAiProfessionalOneTap.mockImplementation(async () => {
      generationStarted = true
      currentDraft = professionalDraft({
        revision: 6,
        latest_export: {
          id: 'exp-pro-2',
          draft_id: 'draft-pdf',
          filename: 'FR-LAVN_r6_techpack.pdf',
          byte_size: 1200,
          page_count: 4,
          revision: 6,
          status: 'READY',
          verification: 'UNVERIFIED',
          metadata: { is_professional: true },
          created_at: '2026-10-27T13:00:00Z',
        },
        spec: {
          ...professionalDraft().spec,
          ai: {
            last_run_id: 'run-pro-2',
            last_mode: 'professional',
            export_id: 'exp-pro-2',
            dirty_since_generation: false,
            paid_sections: ['professional'],
          },
        },
      })
      return {
        run_id: 'run-pro-2',
        status: 'queued',
        cost_usd_cents: 0,
        mode: 'professional',
        accepted: true,
        progress: { phase: 'preparing', message: 'Analyzing your design…' },
      }
    })
    getTechpackAiRun.mockResolvedValue({
      id: 'run-pro-2',
      draft_id: 'draft-pdf',
      stage: 'professional',
      status: 'completed',
      cost_usd_cents: 55,
      export_id: 'exp-pro-2',
      pdf_ready: true,
      pdf_filename: 'FR-LAVN_r6_techpack.pdf',
      artifacts: [],
      progress: { phase: 'ready', message: 'Your AI Technical Pack is ready' },
      result: { export_id: 'exp-pro-2', pdf_ready: true },
    })
    getTechpackDraft.mockImplementation(async () => structuredClone(currentDraft))

    render(
      <StrictMode>
        <TechpackScreen draftId="draft-pdf" onBack={() => undefined} />
      </StrictMode>,
    )
    expect(await screen.findByRole('button', { name: /Generate AI PDF/i })).toBeInTheDocument()
    expect(generationStarted).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: /Generate AI PDF/i }))
    await waitFor(() => expect(generateTechpackAiProfessionalOneTap).toHaveBeenCalled())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600)
    })
    await waitFor(() => {
      const downloads = screen.getAllByRole('button', { name: /Download PDF/i })
      expect(downloads.length).toBeGreaterThan(0)
    })
    // Main CTA must be Download again (not Generate) after the new run binds.
    expect(screen.queryByRole('button', { name: /Generate AI PDF/i })).not.toBeInTheDocument()
  })
})
