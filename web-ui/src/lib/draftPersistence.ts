import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
  resolveDraftConflict,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  readLocalDraft,
  readStoredDesignId,
  writeLocalDraft,
  writeStoredDesignId,
} from '@/lib/localDraftStore'
import {
  createStudioDraft,
  extractStudioDraft,
  getDesign,
  listMyDesigns,
  pickLatestStudioDraft,
  updateStudioDraft,
} from '@/services/designsApi'

export type RestoreResult = {
  designId: string | null
  document: StudioDraftDocument
  conflict:
    | null
    | {
        local: StudioDraftDocument
        server: StudioDraftDocument
        designId: string
      }
  notice: string | null
}

export async function restoreStudioDraft(userId: string): Promise<RestoreResult> {
  const local = await readLocalDraft(userId)
  const storedId = readStoredDesignId(userId)

  let serverDesignId: string | null = storedId
  let serverDoc: StudioDraftDocument | null = null
  let notice: string | null = null

  try {
    if (storedId) {
      try {
        const design = await getDesign(storedId)
        serverDoc = extractStudioDraft(design)
        serverDesignId = design.id
      } catch {
        serverDesignId = null
      }
    }

    if (!serverDoc) {
      const mine = await listMyDesigns()
      const latest = pickLatestStudioDraft(mine)
      if (latest) {
        serverDesignId = latest.id
        serverDoc = extractStudioDraft(latest)
        writeStoredDesignId(userId, latest.id)
      }
    }
  } catch {
    notice = 'Working offline from this device. Changes save locally until the API is reachable.'
    if (local?.document) {
      return {
        designId: local.designId,
        document: local.document,
        conflict: null,
        notice,
      }
    }
    return {
      designId: null,
      document: createEmptyDraftDocument(),
      conflict: null,
      notice,
    }
  }

  if (local?.document && serverDoc && serverDesignId) {
    const decision = resolveDraftConflict(local.document, serverDoc)
    if (decision.needsUserChoice) {
      return {
        designId: serverDesignId,
        document: local.document,
        conflict: { local: local.document, server: serverDoc, designId: serverDesignId },
        notice: null,
      }
    }
    if (decision.winner === 'local') {
      return {
        designId: serverDesignId,
        document: local.document,
        conflict: null,
        notice: 'Restored newer local recovery draft. Syncing to your private design…',
      }
    }
    if (decision.winner === 'server') {
      return {
        designId: serverDesignId,
        document: serverDoc,
        conflict: null,
        notice: null,
      }
    }
    return {
      designId: serverDesignId,
      document: serverDoc,
      conflict: null,
      notice: null,
    }
  }

  if (serverDoc && serverDesignId) {
    return { designId: serverDesignId, document: serverDoc, conflict: null, notice: null }
  }

  if (local?.document) {
    return {
      designId: local.designId,
      document: local.document,
      conflict: null,
      notice: notice ?? 'Restored local recovery draft.',
    }
  }

  return {
    designId: null,
    document: createEmptyDraftDocument(),
    conflict: null,
    notice: null,
  }
}

export async function persistStudioDraft(args: {
  userId: string
  designId: string | null
  document: StudioDraftDocument
  lastFingerprint: string | null
}): Promise<{ designId: string; document: StudioDraftDocument; fingerprint: string }> {
  const fingerprint = draftContentFingerprint(args.document)
  await writeLocalDraft({
    userId: args.userId,
    designId: args.designId,
    document: args.document,
    savedAt: new Date().toISOString(),
  })

  if (args.lastFingerprint === fingerprint && args.designId) {
    return { designId: args.designId, document: args.document, fingerprint }
  }

  if (args.designId) {
    const updated = await updateStudioDraft(args.designId, args.document)
    writeStoredDesignId(args.userId, updated.id)
    await writeLocalDraft({
      userId: args.userId,
      designId: updated.id,
      document: args.document,
      savedAt: new Date().toISOString(),
    })
    return { designId: updated.id, document: args.document, fingerprint }
  }

  const created = await createStudioDraft(args.document)
  writeStoredDesignId(args.userId, created.id)
  await writeLocalDraft({
    userId: args.userId,
    designId: created.id,
    document: args.document,
    savedAt: new Date().toISOString(),
  })
  return { designId: created.id, document: args.document, fingerprint }
}

export function documentFromEditorState(input: {
  prev: StudioDraftDocument
  strokes: StudioDraftDocument['strokes']
  model: StudioDraftDocument['model']
  customReferenceUrl: string | null
  customReferenceKey: string | null
  sizeId: StudioDraftDocument['brush']['sizeId']
  opacity: number
  color: string
  dimmed: boolean
}): StudioDraftDocument {
  return bumpDraftDocument(input.prev, {
    strokes: input.strokes,
    model: input.model,
    customReferenceUrl: input.customReferenceUrl,
    customReferenceKey: input.customReferenceKey,
    brush: {
      sizeId: input.sizeId,
      opacity: input.opacity,
      color: input.color,
    },
    dimmed: input.dimmed,
  })
}
