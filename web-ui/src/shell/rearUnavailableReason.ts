import type { ModelChoice } from '@/assets/modelLibrary'

/** Honest copy when Flip Paper cannot open a Back croquis for the selected model. */
export function rearUnavailableReasonForModel(model: ModelChoice): string {
  if (model === 'female-atelier') {
    return 'Back view is not available for Female · Atelier yet. Keep sketching on the Front.'
  }
  if (model === 'custom' || model === 'blank' || model === 'female' || model === 'male') {
    return 'Back view is only available for library models with a paired rear croquis.'
  }
  return 'Back view is not available for this model. Keep sketching on the Front.'
}
