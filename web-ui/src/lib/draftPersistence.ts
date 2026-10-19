import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  documentFromEditorState,
  resolveDraftConflict,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  readLocalDraft,
  readStoredDesignId,
  writeLocalDraft,
  writeStoredDesignId,
  type LocalWriteResult,
} from '@/lib/localDraftStore'
import {
  createStudioDraft,
  documentForCloud,
  extractStudioDraft,
  getDesign,
  listMyDesigns,
  parseDraftConflict,
  pickLatestStudioDraft,
  updateStudioDraft,
  type DesignRead,
} from '@/services/designsApi'
import { ApiError } from '@/services/api/client'

export { documentFromEditorState }

export type RestoreResult = {
  designId: string | null
  document: StudioDraftDocument
  /** Last server-acknowledged clientRevision, when known. */
  syncedRevision: number | null
  conflict:
    | null
    | {
        local: StudioDraftDocument
        server: StudioDraftDocument
        designId: string
      }
  notice: string | null
}

export type PersistResult =
  | {
      ok: true
      designId: string
      document: StudioDraftDocument
      fingerprint: string
      syncedRevision: number
      localPersisted: boolean
    }
  | {
      ok: false
      conflict: {
        local: StudioDraftDocument
        server: StudioDraftDocument
        designId: string
      }
      localPersisted: boolean
      error: string
    }
  | {
      ok: false
      conflict: null
      localPersisted: boolean
      error: string
      designId: string | null
    }

const CUSTOM_REF_BETA_NOTICE =
  'Custom reference images are session-only in private beta (not stored privately on the server). Re-select the image after refresh.'

function withCustomRefNotice(doc: StudioDraftDocument, notice: string | null): string | null {
  if (doc.model === 'custom' && !doc.customReferenceUrl && !doc.customReferenceKey) {
    return notice ? `${notice} ${CUSTOM_REF_BETA_NOTICE}` : CUSTOM_REF_BETA_NOTICE
  }
  return notice
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
        syncedRevision: local.syncedRevision,
        conflict: null,
        notice: withCustomRefNotice(local.document, notice),
      }
    }
    return {
      designId: null,
      document: createEmptyDraftDocument(),
      syncedRevision: null,
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
        syncedRevision: local.syncedRevision ?? serverDoc.clientRevision,
        conflict: { local: local.document, server: serverDoc, designId: serverDesignId },
        notice: withCustomRefNotice(local.document, null),
      }
    }
    // Content equal — prefer server snapshot for synced revision tracking.
    return {
      designId: serverDesignId,
      document: serverDoc,
      syncedRevision: serverDoc.clientRevision,
      conflict: null,
      notice: withCustomRefNotice(serverDoc, null),
    }
  }

  if (serverDoc && serverDesignId) {
    return {
      designId: serverDesignId,
      document: serverDoc,
      syncedRevision: serverDoc.clientRevision,
      conflict: null,
      notice: withCustomRefNotice(serverDoc, null),
    }
  }

  if (local?.document) {
    return {
      designId: local.designId,
      document: local.document,
      syncedRevision: local.syncedRevision,
      conflict: null,
      notice: withCustomRefNotice(
        local.document,
        notice ?? 'Restored local recovery draft. Syncing to your private design…',
      ),
    }
  }

  return {
    designId: null,
    document: createEmptyDraftDocument(),
    syncedRevision: null,
    conflict: null,
    notice: null,
  }
}

/**
 * Durable local write independent of API debounce. Returns whether IndexedDB accepted the row.
 */
export async function persistLocalRecovery(args: {
  userId: string
  designId: string | null
  document: StudioDraftDocument
  syncedRevision: number | null
}): Promise<LocalWriteResult> {
  return writeLocalDraft({
    userId: args.userId,
    designId: args.designId,
    document: args.document,
    savedAt: new Date().toISOString(),
    syncedRevision: args.syncedRevision,
  })
}

/**
 * Ensure a single owner-scoped Studio working draft exists.
 * Reconciles lost POST responses by listing/updating instead of creating duplicates.
 */
export async function ensureStudioDraft(
  userId: string,
  document: StudioDraftDocument,
  preferredDesignId: string | null,
  expectedRevision: number | null,
): Promise<DesignRead> {
  const cloudDoc = documentForCloud(document)

  if (preferredDesignId) {
    try {
      return await updateStudioDraft(preferredDesignId, cloudDoc, {
        expectedRevision: expectedRevision ?? undefined,
      })
    } catch (err) {
      const conflict = parseDraftConflict(err)
      if (conflict) throw err
      // Fall through to list/create if the preferred id vanished.
    }
  }

  let existing: DesignRead | null = null
  try {
    const mine = await listMyDesigns()
    existing = pickLatestStudioDraft(mine)
  } catch {
    existing = null
  }

  if (existing) {
    writeStoredDesignId(userId, existing.id)
    const serverDoc = extractStudioDraft(existing)
    return updateStudioDraft(existing.id, cloudDoc, {
      expectedRevision: serverDoc?.clientRevision ?? expectedRevision ?? undefined,
    })
  }

  try {
    const created = await createStudioDraft(cloudDoc)
    writeStoredDesignId(userId, created.id)
    return created
  } catch (createErr) {
    // Response may have been lost after a successful create — reconcile.
    try {
      const mine = await listMyDesigns()
      const recovered = pickLatestStudioDraft(mine)
      if (recovered) {
        writeStoredDesignId(userId, recovered.id)
        const serverDoc = extractStudioDraft(recovered)
        return updateStudioDraft(recovered.id, cloudDoc, {
          expectedRevision: serverDoc?.clientRevision ?? undefined,
        })
      }
    } catch {
      /* rethrow original */
    }
    throw createErr
  }
}

export async function persistStudioDraft(args: {
  userId: string
  designId: string | null
  document: StudioDraftDocument
  /** Authoritative fingerprint of the document being saved (from ref, not React). */
  fingerprint: string
  /** Last fingerprint successfully acknowledged by the API for this design. */
  lastSyncedFingerprint: string | null
  expectedRevision: number | null
  /** When true, skip local write (caller already persisted). */
  skipLocalWrite?: boolean
}): Promise<PersistResult> {
  const cloudDoc = documentForCloud(args.document)
  const cloudFingerprint = draftContentFingerprint(cloudDoc)

  let localPersisted = Boolean(args.skipLocalWrite)
  if (!args.skipLocalWrite) {
    const local = await persistLocalRecovery({
      userId: args.userId,
      designId: args.designId,
      document: args.document,
      syncedRevision: args.expectedRevision,
    })
    localPersisted = local.ok
  }

  if (args.lastSyncedFingerprint === cloudFingerprint && args.designId) {
    return {
      ok: true,
      designId: args.designId,
      document: cloudDoc,
      fingerprint: cloudFingerprint,
      syncedRevision: cloudDoc.clientRevision,
      localPersisted,
    }
  }

  try {
    const saved = await ensureStudioDraft(
      args.userId,
      cloudDoc,
      args.designId,
      args.expectedRevision,
    )
    writeStoredDesignId(args.userId, saved.id)
    const extracted = extractStudioDraft(saved) ?? cloudDoc
    const localAfter = await writeLocalDraft({
      userId: args.userId,
      designId: saved.id,
      document: args.document,
      savedAt: new Date().toISOString(),
      syncedRevision: extracted.clientRevision,
    })
    return {
      ok: true,
      designId: saved.id,
      document: extracted,
      fingerprint: draftContentFingerprint(documentForCloud(extracted)),
      syncedRevision: extracted.clientRevision,
      localPersisted: localPersisted || localAfter.ok,
    }
  } catch (err) {
    const conflictPayload = parseDraftConflict(err)
    if (conflictPayload) {
      const serverDoc =
        extractStudioDraft(conflictPayload.design) ?? createEmptyDraftDocument()
      return {
        ok: false,
        conflict: {
          local: args.document,
          server: serverDoc,
          designId: conflictPayload.design.id,
        },
        localPersisted,
        error:
          err instanceof ApiError
            ? err.message
            : 'Draft was updated elsewhere. Resolve the conflict before saving again.',
      }
    }
    const message =
      err instanceof ApiError
        ? err.message
        : 'Save failed. Your latest edits are kept on this device when local storage is available.'
    return {
      ok: false,
      conflict: null,
      localPersisted,
      error: message,
      designId: args.designId,
    }
  }
}
