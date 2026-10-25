import { ApiError } from '@/services/api/client'
import {
  enqueueSketchPolish,
  enqueueSketchPolishDual,
  type PolishSketchDualInput,
  type SketchPolishDualRead,
} from '@/services/ai/magicApi'

export type DualPolishEnqueueMode = 'dual' | 'sequential'

export type DualPolishEnqueueResult = {
  mode: DualPolishEnqueueMode
  magic_operation_id: string
  front_job_id: string
  back_job_id: string
}

/**
 * Prefer coordinated dual enqueue; fall back to two `/sketch/polish` calls when the
 * dual route is not deployed (404).
 */
export async function enqueueDualOrSequentialPolish(
  input: PolishSketchDualInput,
): Promise<DualPolishEnqueueResult> {
  try {
    const dual = await enqueueSketchPolishDual(input)
    return toEnqueueResult('dual', dual)
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 404) throw err
    const operationId =
      input.magic_operation_id ??
      (typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `magic_op_${Date.now()}`)
    const front = await enqueueSketchPolish({
      imageBase64: input.front.image_base64,
      notes: input.front.notes ?? input.notes ?? 'polish concept (front)',
      designId: input.design_id ?? null,
      magic_operation_id: operationId,
      studio_side: 'front',
      reference_model_id: input.reference_model_id,
      signal: input.signal,
    })
    const back = await enqueueSketchPolish({
      imageBase64: input.back.image_base64,
      notes: input.back.notes ?? input.notes ?? 'polish concept (back)',
      designId: input.design_id ?? null,
      magic_operation_id: operationId,
      studio_side: 'back',
      reference_model_id: input.reference_model_id,
      signal: input.signal,
    })
    return {
      mode: 'sequential',
      magic_operation_id: operationId,
      front_job_id: front.id,
      back_job_id: back.id,
    }
  }
}

function toEnqueueResult(mode: 'dual', dual: SketchPolishDualRead): DualPolishEnqueueResult {
  return {
    mode,
    magic_operation_id: dual.magic_operation_id,
    front_job_id: dual.front_job.id,
    back_job_id: dual.back_job.id,
  }
}
