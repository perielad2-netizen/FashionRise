/**
 * Request-counting regression: idle editor / tab switches must not PATCH.
 * Real edits debounce to one save; success must not re-trigger; Done is quiet when clean.
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

const V2_DRAFT = {
  id: 'draft-loop',
  user_id: 'u1',
  look_id: 'look-1',
  design_id: null,
  title: 'Lavender hoodie set',
  style_code: 'FR-LAVN',
  revision: 3,
  status: 'DRAFT',
  verification: 'UNVERIFIED',
  spec: {
    schema_version: '2.0',
    workflow_stage: 'understand',
    units: 'cm',
    size_system: 'EU',
    sample_size: '',
    look_notes: 'lavender hoodie and golden yellow shorts',
    designer_notes: '',
    outfit: {
      piece_count: 2,
      pieces: [
        {
          id: 'piece-top',
          category: 'hoodie',
          label: 'Lavender Hoodie',
          color_hint: 'lavender-purple',
          detection_source: 'ai_vision',
          materials: { shell: { name: 'french terry', source: 'ai_inferred' } },
          closures: { type: '', source: 'empty' },
          fit: { silhouette: 'relaxed' },
          finished_measurements: {
            chest_bust: { value: null, unit: 'cm', source: 'empty' },
          },
        },
        {
          id: 'piece-bottom',
          category: 'shorts',
          label: 'Yellow Shorts',
          color_hint: 'golden-yellow',
          detection_source: 'ai_vision',
          materials: { shell: { name: 'cotton', source: 'ai_inferred' } },
          closures: { type: '', source: 'empty' },
          fit: { silhouette: '' },
          finished_measurements: {
            waist: { value: null, unit: 'cm', source: 'empty' },
          },
        },
      ],
      detection_confidence: 'high',
      needs_user_confirm: false,
    },
    body: {
      height: { value: null, unit: 'cm', source: 'empty' },
      waist: { value: null, unit: 'cm', source: 'empty' },
    },
    preferences: { fit_preference: 'regular', notes: '' },
    warnings: [],
    ai: { last_run_id: null, paid_sections: [] },
  },
  front_job_id: 'job-f',
  back_job_id: null,
  created_at: '2026-10-27T12:00:00Z',
  updated_at: '2026-10-27T12:00:00Z',
  latest_export: null,
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

async function openEditor() {
  render(
    <StrictMode>
      <TechpackScreen draftId="draft-loop" onBack={() => undefined} />
    </StrictMode>,
  )
  await screen.findByText('Create Real Design')
  fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
  return screen.findByRole('dialog', { name: /Measurements & details/i })
}

describe.each([
  ['mobile', 390],
  ['tablet', 768],
  ['desktop', 1366],
] as const)('TechpackScreen autosave quiet (%s %dpx)', (_label, width) => {
  let currentDraft: typeof V2_DRAFT

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubMatchMedia(width)
    currentDraft = structuredClone(V2_DRAFT)
    getTechpackDraft.mockReset()
    updateTechpackDraft.mockReset()
    getTechpackAiStatus.mockReset()
    getLatestTechpackAiRun.mockReset()
    getLatestTechpackAiRun.mockResolvedValue(null)
    getTechpackDraft.mockImplementation(async () => structuredClone(currentDraft))
    getTechpackAiStatus.mockResolvedValue({
      enabled: true,
      professional_available: true,
      max_usd_per_run: 8,
      note: 'ok',
    })
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      // Simulate server returning a fresh object graph (new references) every time.
      currentDraft = {
        ...currentDraft,
        revision: currentDraft.revision + 1,
        title: (patch.title as string) ?? currentDraft.title,
        style_code: (patch.style_code as string) ?? currentDraft.style_code,
        spec: patch.spec
          ? ({ ...currentDraft.spec, ...(patch.spec as object) } as typeof currentDraft.spec)
          : currentDraft.spec,
        updated_at: new Date().toISOString(),
      }
      return structuredClone(currentDraft)
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('open + idle 60s → 0 update requests; no Saving/Saved chrome', async () => {
    const dialog = await openEditor()
    expect(within(dialog).queryByText(/Saving/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/^Saved$/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/Edits save automatically/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/autosave on/i)).not.toBeInTheDocument()
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
  })

  it('switch tabs and garments without editing → 0 updates', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()

    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    fireEvent.click(within(dialog).getByRole('tab', { name: /Preferences/i }))
    fireEvent.click(within(dialog).getByRole('tab', { name: /^Garments$/i }))
    // Garment piece controls use role=tab; prefer text match (em dash labels).
    const bottom = within(dialog).getAllByText(/Yellow Shorts/i)[0]
    fireEvent.click(bottom)
    const top = within(dialog).getAllByText(/Lavender Hoodie/i)[0]
    fireEvent.click(top)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
  })

  it('edit one field → 1 debounced save; idle 60s after → still 1; no success chrome', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()

    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '170' } })

    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(1))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(updateTechpackDraft).toHaveBeenCalledTimes(1)
    expect(within(dialog).queryByText(/Saving/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/^Saved$/i)).not.toBeInTheDocument()
  })

  it('rapid typing coalesces into one save of the latest value', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)

    fireEvent.change(height, { target: { value: '1' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    fireEvent.change(height, { target: { value: '17' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    fireEvent.change(height, { target: { value: '170' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(1))
    const patch = updateTechpackDraft.mock.calls[0][1] as {
      spec: { body: { height: { value: number | string | null } } }
    }
    expect(String(patch.spec.body.height.value)).toBe('170')
  })

  it('Done with no changes closes immediately with 0 requests', async () => {
    await openEditor()
    updateTechpackDraft.mockClear()
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
  })

  it('Done with pending changes flushes once then closes', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '168' } })
    // Flush before debounce fires.
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(1))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    expect(updateTechpackDraft).toHaveBeenCalledTimes(1)
  })

  it('failed save shows error, retains data, allows retry', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()
    updateTechpackDraft.mockRejectedValueOnce(new Error('network down'))
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value: '165' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    expect(await within(dialog).findByTestId('details-save-error')).toHaveTextContent(/network down/i)
    expect(height).toHaveValue('165')

    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      currentDraft = {
        ...currentDraft,
        revision: currentDraft.revision + 1,
        title: (patch.title as string) ?? currentDraft.title,
        style_code: (patch.style_code as string) ?? currentDraft.style_code,
        spec: patch.spec
          ? ({ ...currentDraft.spec, ...(patch.spec as object) } as typeof currentDraft.spec)
          : currentDraft.spec,
      }
      return structuredClone(currentDraft)
    })
    fireEvent.click(within(dialog).getByRole('button', { name: /Retry save/i }))
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(2))
    await waitFor(() =>
      expect(within(dialog).queryByTestId('details-save-error')).not.toBeInTheDocument(),
    )
  })
})
