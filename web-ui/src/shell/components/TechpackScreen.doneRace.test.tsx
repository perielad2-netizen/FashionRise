/**
 * Done/Escape save-race hardening: close only after the latest editable snapshot
 * is persisted; no overlapping PATCHes; failures keep the editor open.
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
  latest_export: null
}

const BASE_DRAFT: Draft = {
  id: 'draft-race',
  user_id: 'u1',
  look_id: 'look-1',
  design_id: null,
  title: 'Race draft',
  style_code: 'FR-RACE',
  revision: 1,
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
          category: 'dress',
          label: 'Cream Dress',
          materials: { shell: { name: '', source: 'empty' } },
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

function heightFromPatch(patch: Record<string, unknown>): string {
  const spec = patch.spec as { body?: { height?: { value?: unknown } } }
  return String(spec?.body?.height?.value ?? '')
}

function applyPatchToDraft(current: Draft, patch: Record<string, unknown>, revision: number): Draft {
  return {
    ...current,
    revision,
    title: (patch.title as string) ?? current.title,
    style_code: (patch.style_code as string) ?? current.style_code,
    spec: patch.spec
      ? ({ ...current.spec, ...(patch.spec as object) } as Record<string, unknown>)
      : current.spec,
    updated_at: new Date().toISOString(),
  }
}

describe.each([
  ['mobile', 390],
  ['tablet', 768],
  ['desktop', 1366],
] as const)('TechpackScreen Done/save race (%s %dpx)', (_label, width) => {
  let currentDraft: Draft
  let inFlight = 0
  let maxInFlight = 0

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubMatchMedia(width)
    currentDraft = structuredClone(BASE_DRAFT)
    inFlight = 0
    maxInFlight = 0
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
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      try {
        currentDraft = applyPatchToDraft(currentDraft, patch, currentDraft.revision + 1)
        return structuredClone(currentDraft)
      } finally {
        inFlight -= 1
      }
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  async function openEditor() {
    render(
      <StrictMode>
        <TechpackScreen draftId="draft-race" onBack={() => undefined} />
      </StrictMode>,
    )
    await screen.findByText('Create Real Design')
    fireEvent.click(screen.getByRole('button', { name: /Edit measurements & details/i }))
    return screen.findByRole('dialog', { name: /Measurements & details/i })
  }

  async function setHeight(dialog: HTMLElement, value: string) {
    fireEvent.click(within(dialog).getByRole('tab', { name: /Body measurements/i }))
    const height = await within(dialog).findByLabelText(/^Height$/i)
    fireEvent.change(height, { target: { value } })
    return height
  }

  it('clean Done → zero PATCH, immediate close', async () => {
    await openEditor()
    updateTechpackDraft.mockClear()
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    expect(updateTechpackDraft).toHaveBeenCalledTimes(0)
    expect(maxInFlight).toBeLessThanOrEqual(1)
  })

  it('dirty Done → one PATCH, close on success', async () => {
    const dialog = await openEditor()
    updateTechpackDraft.mockClear()
    await setHeight(dialog, '170')
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(updateTechpackDraft).toHaveBeenCalledTimes(1))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    expect(updateTechpackDraft).toHaveBeenCalledTimes(1)
    expect(heightFromPatch(updateTechpackDraft.mock.calls[0][1] as Record<string, unknown>)).toBe(
      '170',
    )
    expect(maxInFlight).toBe(1)
  })

  it('edit A → Done → edit B while A unresolved → B persists before close', async () => {
    let releaseA!: () => void
    const gateA = new Promise<void>((resolve) => {
      releaseA = resolve
    })
    let calls = 0
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      calls += 1
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      try {
        if (calls === 1) await gateA
        currentDraft = applyPatchToDraft(currentDraft, patch, currentDraft.revision + 1)
        return structuredClone(currentDraft)
      } finally {
        inFlight -= 1
      }
    })

    const dialog = await openEditor()
    updateTechpackDraft.mockClear()
    calls = 0
    const height = await setHeight(dialog, '160')
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(calls).toBe(1))

    // Newer edit while Done's first PATCH is still open.
    fireEvent.change(height, { target: { value: '165' } })
    // Also hammer Done/Escape while flush is pending — must not duplicate writers.
    fireEvent.click(screen.getByTestId('details-done'))
    fireEvent.keyDown(window, { key: 'Escape' })

    releaseA()

    await waitFor(() => expect(updateTechpackDraft.mock.calls.length).toBeGreaterThanOrEqual(2))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    const last = updateTechpackDraft.mock.calls.at(-1)?.[1] as Record<string, unknown>
    expect(heightFromPatch(last)).toBe('165')
    expect(maxInFlight).toBe(1)
  })

  it('same A→Done→B scenario but PATCH B fails → editor stays open with B + error', async () => {
    let releaseA!: () => void
    const gateA = new Promise<void>((resolve) => {
      releaseA = resolve
    })
    let calls = 0
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      calls += 1
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      try {
        if (calls === 1) {
          await gateA
          currentDraft = applyPatchToDraft(currentDraft, patch, currentDraft.revision + 1)
          return structuredClone(currentDraft)
        }
        throw new Error('network down on B')
      } finally {
        inFlight -= 1
      }
    })

    const dialog = await openEditor()
    const height = await setHeight(dialog, '160')
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(calls).toBe(1))
    fireEvent.change(height, { target: { value: '168' } })
    releaseA()

    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2))
    expect(await screen.findByTestId('details-save-error')).toHaveTextContent(/network down on B/i)
    expect(screen.getByRole('dialog', { name: /Measurements & details/i })).toBeInTheDocument()
    expect(height).toHaveValue('168')
    expect(maxInFlight).toBe(1)
  })

  it('Done while background PATCH in flight → no overlap; latest values persisted', async () => {
    let releaseBg!: () => void
    const gateBg = new Promise<void>((resolve) => {
      releaseBg = resolve
    })
    let calls = 0
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      calls += 1
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      try {
        if (calls === 1) await gateBg
        currentDraft = applyPatchToDraft(currentDraft, patch, currentDraft.revision + 1)
        return structuredClone(currentDraft)
      } finally {
        inFlight -= 1
      }
    })

    const dialog = await openEditor()
    const height = await setHeight(dialog, '150')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    await waitFor(() => expect(calls).toBe(1))

    fireEvent.change(height, { target: { value: '155' } })
    fireEvent.click(screen.getByTestId('details-done'))
    // Background still open — Done must wait, not start a parallel PATCH.
    expect(calls).toBe(1)
    expect(maxInFlight).toBe(1)

    releaseBg()
    await waitFor(() => expect(updateTechpackDraft.mock.calls.length).toBeGreaterThanOrEqual(2))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    const last = updateTechpackDraft.mock.calls.at(-1)?.[1] as Record<string, unknown>
    expect(heightFromPatch(last)).toBe('155')
    expect(maxInFlight).toBe(1)
  })

  it('repeated Done/Escape while saving → no duplicate writes or premature close', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let calls = 0
    updateTechpackDraft.mockImplementation(async (_id: string, patch: Record<string, unknown>) => {
      calls += 1
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      try {
        await gate
        currentDraft = applyPatchToDraft(currentDraft, patch, currentDraft.revision + 1)
        return structuredClone(currentDraft)
      } finally {
        inFlight -= 1
      }
    })

    const dialog = await openEditor()
    await setHeight(dialog, '140')
    fireEvent.click(screen.getByTestId('details-done'))
    await waitFor(() => expect(calls).toBe(1))
    fireEvent.click(screen.getByTestId('details-done'))
    fireEvent.click(screen.getByTestId('details-done'))
    fireEvent.keyDown(window, { key: 'Escape' })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(calls).toBe(1)
    expect(screen.getByRole('dialog', { name: /Measurements & details/i })).toBeInTheDocument()

    release()
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Measurements & details/i })).not.toBeInTheDocument(),
    )
    expect(updateTechpackDraft).toHaveBeenCalledTimes(1)
    expect(maxInFlight).toBe(1)
  })
})
