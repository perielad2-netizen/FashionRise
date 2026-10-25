import { ApiError } from '@/services/api/client'
import {
  enqueueSketchPolishDual,
  type PolishSketchDualInput,
  type SketchPolishDualRead,
} from '@/services/ai/magicApi'

export type DualPolishEnqueueResult = {
  magic_operation_id: string
  front_job_id: string
  back_job_id: string
}

export class DualPolishUnavailableError extends Error {
  constructor(message = 'Dual Magic is not available on this server. Update the app when dual polish ships.') {
    super(message)
    this.name = 'DualPolishUnavailableError'
  }
}

/**
 * Coordinated dual enqueue only — no sequential `/sketch/polish` fallback.
 */
export async function enqueueDualPolish(
  input: PolishSketchDualInput,
): Promise<DualPolishEnqueueResult> {
  try {
    const dual = await enqueueSketchPolishDual(input)
    return toEnqueueResult(dual)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      throw new DualPolishUnavailableError()
    }
    throw err
  }
}

/** @deprecated Use enqueueDualPolish */
export const enqueueDualOrSequentialPolish = enqueueDualPolish

function toEnqueueResult(dual: SketchPolishDualRead): DualPolishEnqueueResult {
  return {
    magic_operation_id: dual.magic_operation_id,
    front_job_id: dual.front_job.id,
    back_job_id: dual.back_job.id,
  }
}
