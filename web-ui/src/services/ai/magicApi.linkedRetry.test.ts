import { afterEach, describe, expect, it, vi } from 'vitest'
import { enqueueSketchPolish, enqueueSketchPolishDual } from '@/services/ai/magicApi'
import * as client from '@/services/api/client'

describe('enqueueSketchPolish linked retry fields', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('forwards idempotency key, identity, and garment spec for linked /polish', async () => {
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValue({
      id: 'job-1',
      status: 'queued',
      job_type: 'sketch_polish',
      created_at: new Date().toISOString(),
      input_data: {},
    } as never)

    await enqueueSketchPolish({
      imageBase64: 'data:image/png;base64,xx',
      designId: 'design-1',
      magic_operation_id: 'op-1',
      studio_side: 'back',
      idempotency_key: 'op-1:back:retry:abc',
      source_revision: 4,
      content_fingerprint: 'fp-abc',
      reference_model_id: 'female-straight',
      shared_garment_spec: { garment_category: 'studio', main_colors: ['#111'] },
      notes: 'polish concept (back) retry',
    })

    expect(spy).toHaveBeenCalledTimes(1)
    const [, opts] = spy.mock.calls[0]!
    expect(opts?.method).toBe('POST')
    const body = opts?.body as {
      design_id: string
      input_data: Record<string, unknown>
    }
    expect(body.design_id).toBe('design-1')
    expect(body.input_data).toMatchObject({
      magic_operation_id: 'op-1',
      studio_side: 'back',
      idempotency_key: 'op-1:back:retry:abc',
      source_revision: 4,
      content_fingerprint: 'fp-abc',
      reference_model_id: 'female-straight',
      shared_garment_spec: { garment_category: 'studio', main_colors: ['#111'] },
    })
  })

  it('keeps ordinary Front-only polish without linked fields', async () => {
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValue({
      id: 'job-solo',
      status: 'queued',
      job_type: 'sketch_polish',
      created_at: new Date().toISOString(),
      input_data: {},
    } as never)

    await enqueueSketchPolish({
      imageBase64: 'data:image/png;base64,yy',
      notes: 'polish concept',
    })

    const body = (spy.mock.calls[0]![1] as { body: { input_data: Record<string, unknown> } }).body
    expect(body.input_data.image_base64).toBe('data:image/png;base64,yy')
    expect(body.input_data.idempotency_key).toBeUndefined()
    expect(body.input_data.magic_operation_id).toBeUndefined()
  })

  it('forwards garment spec and fabric swatch on Front-only polish', async () => {
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValue({
      id: 'job-fabric',
      status: 'queued',
      job_type: 'sketch_polish',
      created_at: new Date().toISOString(),
      input_data: {},
    } as never)

    await enqueueSketchPolish({
      imageBase64: 'data:image/png;base64,sketch',
      fabricSwatchBase64: 'data:image/png;base64,swatch',
      notes: 'polish concept',
      studio_side: 'front',
      reference_model_id: 'female-hand-hip',
      shared_garment_spec: {
        garment_category: 'studio',
        main_colors: ['#BE185D'],
        materials: ['Satin repeating textile (exact Studio tile reference)'],
      },
      source_revision: 3,
      content_fingerprint: 'fp-satin',
    })

    const body = (spy.mock.calls[0]![1] as { body: { input_data: Record<string, unknown> } }).body
    expect(body.input_data).toMatchObject({
      image_base64: 'data:image/png;base64,sketch',
      fabric_swatch_base64: 'data:image/png;base64,swatch',
      studio_side: 'front',
      shared_garment_spec: {
        main_colors: ['#BE185D'],
        materials: ['Satin repeating textile (exact Studio tile reference)'],
      },
      source_revision: 3,
      content_fingerprint: 'fp-satin',
    })
    expect(body.input_data.idempotency_key).toBeUndefined()
  })

  it('forwards independent fabric swatches on Dual Magic polish-dual', async () => {
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValue({
      magic_operation_id: 'op-dual-fabric',
      front_job: {
        id: 'jf',
        status: 'queued',
        job_type: 'sketch_polish',
        created_at: new Date().toISOString(),
        input_data: {},
      },
      back_job: {
        id: 'jb',
        status: 'queued',
        job_type: 'sketch_polish',
        created_at: new Date().toISOString(),
        input_data: {},
      },
    } as never)

    await enqueueSketchPolishDual({
      magic_operation_id: 'op-dual-fabric',
      shared_garment_spec: {
        garment_category: 'studio',
        main_colors: ['#BE185D'],
        materials: ['Satin repeating textile (exact Studio tile reference)'],
      },
      source_revision: 2,
      content_fingerprint: 'fp-dual',
      front: {
        image_base64: 'data:image/png;base64,frontSketch',
        fabric_swatch_base64: 'data:image/png;base64,frontSwatch',
        idempotency_key: 'op-dual-fabric:front',
      },
      back: {
        image_base64: 'data:image/png;base64,backSketch',
        fabric_swatch_base64: 'data:image/png;base64,backSwatch',
        idempotency_key: 'op-dual-fabric:back',
      },
    })

    expect(spy).toHaveBeenCalledTimes(1)
    const [path, opts] = spy.mock.calls[0]!
    expect(path).toBe('/ai/sketch/polish-dual')
    const body = opts?.body as {
      front: Record<string, unknown>
      back: Record<string, unknown>
      shared_garment_spec: Record<string, unknown>
    }
    expect(body.front.fabric_swatch_base64).toBe('data:image/png;base64,frontSwatch')
    expect(body.back.fabric_swatch_base64).toBe('data:image/png;base64,backSwatch')
    expect(body.front.image_base64).toBe('data:image/png;base64,frontSketch')
    expect(body.back.image_base64).toBe('data:image/png;base64,backSketch')
    expect(body.shared_garment_spec.main_colors).toEqual(['#BE185D'])
  })
})
