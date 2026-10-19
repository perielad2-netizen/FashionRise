export type ModelChoice = 'female' | 'male' | 'custom' | 'blank'

export type ModelCardKind = 'production' | 'placeholder'

export type ModelLibraryCard = {
  id: string
  label: string
  src: string
  filter: 'all' | 'female' | 'male' | 'utility'
  kind: ModelCardKind
  choice?: ModelChoice
}
