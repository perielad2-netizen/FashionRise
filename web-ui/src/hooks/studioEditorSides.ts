import { canvasSrcForModel, modelHasRearAsset, type ModelChoice } from '@/assets/modelLibrary'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import {
  backArtworkFromDoc,
  documentFromEditorState,
  documentHasBackInk,
  frontArtworkFromDoc,
  isStudioDraftV2,
  normalizeActiveSide,
  STUDIO_DRAFT_SCHEMA_V2,
  upgradeDraftToV2,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { cloneSideBag, sideHasInk, type StudioPaperSide, type StudioSideBag } from '@/lib/studioSideArtwork'
import type { FillOp } from '@/lib/fills'
import type { BrushSizeId, Stroke } from '@/lib/strokes'

/** Canonical per-side ink in the editor — never alias front/back into one buffer. */
export type EditorSideState = {
  activeSide: StudioPaperSide
  frontStrokes: Stroke[]
  frontFills: FillOp[]
  backStrokes: Stroke[]
  backFills: FillOp[]
}

export function rearReferenceAvailable(model: ModelChoice): boolean {
  return isStudioFrontBackEnabled() && modelHasRearAsset(model)
}

export function referenceUrlForModelSide(
  model: ModelChoice,
  side: StudioPaperSide,
  customUrl: string | null,
): string | null {
  if (model === 'custom') return customUrl
  if (model === 'blank') return null
  if (!isStudioFrontBackEnabled()) return canvasSrcForModel(model, 'front')
  if (side === 'back') {
    if (!modelHasRearAsset(model)) return null
    return canvasSrcForModel(model, 'back')
  }
  return canvasSrcForModel(model, 'front')
}

export function sideStateFromDocument(doc: StudioDraftDocument): EditorSideState {
  const activeSide = normalizeActiveSide(doc)
  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  return {
    activeSide,
    frontStrokes: front.strokes,
    frontFills: front.fills,
    backStrokes: back.strokes,
    backFills: back.fills,
  }
}

export function visibleInkFromState(state: EditorSideState): { strokes: Stroke[]; fills: FillOp[] } {
  if (state.activeSide === 'back') {
    return { strokes: state.backStrokes, fills: state.backFills }
  }
  return { strokes: state.frontStrokes, fills: state.frontFills }
}

export function activeArtwork(state: EditorSideState): StudioSideBag {
  return visibleInkFromState(state)
}

export function documentHasAnyInk(doc: StudioDraftDocument): boolean {
  const front = frontArtworkFromDoc(doc)
  if (sideHasInk(front)) return true
  return documentHasBackInk(doc)
}

export function buildDocumentFromEditor(args: {
  prev: StudioDraftDocument
  state: EditorSideState
  model: ModelChoice
  customReferenceUrl: string | null
  customReferenceKey: string | null
  sizeId: BrushSizeId
  sizePx: number
  opacity: number
  color: string
  dimmed: boolean
  clearBackIntent?: boolean
}): StudioDraftDocument {
  const frontBack = isStudioFrontBackEnabled()
  let schema = args.prev.schema
  let activeSide = args.state.activeSide
  let back: StudioSideBag | undefined = args.prev.back

  const frontBag: StudioSideBag = {
    strokes: args.state.frontStrokes,
    fills: args.state.frontFills,
  }
  const backBag: StudioSideBag = {
    strokes: args.state.backStrokes,
    fills: args.state.backFills,
  }

  if (frontBack) {
    const needsV2 =
      isStudioDraftV2(args.prev) ||
      args.state.activeSide === 'back' ||
      sideHasInk(backBag) ||
      args.clearBackIntent
    if (needsV2) schema = STUDIO_DRAFT_SCHEMA_V2
    if (schema === STUDIO_DRAFT_SCHEMA_V2) {
      back = cloneSideBag(backBag)
      activeSide = args.state.activeSide
    }
  }

  const doc = documentFromEditorState({
    prev: args.prev,
    schema,
    strokes: frontBag.strokes,
    fills: frontBag.fills,
    back,
    activeSide: frontBack && schema === STUDIO_DRAFT_SCHEMA_V2 ? activeSide : undefined,
    clearBackIntent: args.clearBackIntent,
    model: args.model,
    customReferenceUrl: args.customReferenceUrl,
    customReferenceKey: args.customReferenceKey,
    sizeId: args.sizeId,
    sizePx: args.sizePx,
    opacity: args.opacity,
    color: args.color,
    dimmed: args.dimmed,
  })

  if (frontBack && schema === STUDIO_DRAFT_SCHEMA_V2) {
    return upgradeDraftToV2(doc)
  }
  return doc
}

export function switchEditorSide(
  state: EditorSideState,
  nextSide: StudioPaperSide,
): EditorSideState {
  if (nextSide === state.activeSide) return state
  return { ...state, activeSide: nextSide }
}

export function patchActiveSideInk(
  state: EditorSideState,
  strokes: Stroke[],
  fills: FillOp[],
): EditorSideState {
  if (state.activeSide === 'back') {
    return { ...state, backStrokes: strokes, backFills: fills }
  }
  return { ...state, frontStrokes: strokes, frontFills: fills }
}

export function emptyBackBagIfClearing(
  prevDoc: StudioDraftDocument,
  nextBack: StudioSideBag,
): boolean {
  const hadInk = documentHasBackInk(prevDoc)
  const nowEmpty = !sideHasInk(nextBack)
  return hadInk && nowEmpty
}
