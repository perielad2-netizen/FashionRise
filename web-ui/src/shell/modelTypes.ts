export type {
  BuiltinModelId,
  ModelChoice,
  ModelGender,
  UtilityModelId,
} from '@/assets/modelLibrary'

export type ModelLibraryCard = {
  id: string
  label: string
  pose?: string
  src: string
  filter: 'all' | 'female' | 'male' | 'utility'
  /** Every listed card is selectable — no unavailable placeholders. */
  choice: import('@/assets/modelLibrary').ModelChoice
}
