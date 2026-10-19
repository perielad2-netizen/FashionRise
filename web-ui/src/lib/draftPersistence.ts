import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  documentFromEditorState,
  rebaseChosenLocalDraft,
  resolveDraftConflict,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  readLocalDraft,
  readStoredDesignId,
  replaceLocalDraft,
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

export { documentFromEditorState, rebaseChosenLocalDraft }

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

function isNotFoundError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404
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
 * Non-409 failures on a known design id do not blind-overwrite via list fallback.
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
      let token = expectedRevision
      if (token == null) {
        // Never PUT a Studio draft without a server-acked revision token.
        const current = await getDesign(preferredDesignId)
        const serverDoc = extractStudioDraft(current)
        if (!serverDoc) {
          throw new ApiError('Preferred design is not a Studio working draft.', 409, null)
        }
        token = serverDoc.clientRevision
      }
      return await updateStudioDraft(preferredDesignId, cloudDoc, {
        expectedRevision: token,
      })
    } catch (err) {
      if (parseDraftConflict(err)) throw err
      // Only fall through when the preferred row is gone — never blind-reconcile on 5xx/network.
      if (!isNotFoundError(err)) throw err
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
    const serverRev = serverDoc?.clientRevision
    if (serverRev == null) {
      throw new ApiError('Studio draft is missing a server revision.', 409, null)
    }
    return updateStudioDraft(existing.id, cloudDoc, {
      expectedRevision: serverRev,
    })
  }

  try {
    const created = await createStudioDraft(cloudDoc)
    writeStoredDesignId(userId, created.id)
    return created
  } catch (createErr) {
    // Response may have been lost after a successful create — reconcile carefully.
    if (parseDraftConflict(createErr)) throw createErr
    try {
      const mine = await listMyDesigns()
      const recovered = pickLatestStudioDraft(mine)
      if (recovered) {
        writeStoredDesignId(userId, recovered.id)
        const serverDoc = extractStudioDraft(recovered)
        if (!serverDoc) throw createErr
        const serverRev = serverDoc.clientRevision
        // Only advance when our content is a strict newer revision; otherwise surface conflict.
        if (cloudDoc.clientRevision < serverRev) {
          return recovered
        }
        if (cloudDoc.clientRevision === serverRev) {
          const same =
            draftContentFingerprint(documentForCloud(serverDoc)) ===
            draftContentFingerprint(cloudDoc)
          if (same) return recovered
          throw createErr instanceof ApiError
            ? createErr
            : new ApiError(
                'Studio working draft already exists with different content at this revision.',
                409,
                {
                  detail: {
                    code: 'conflict',
                    message:
                      'Studio working draft already exists with different content at this revision.',
                    payload: {
                      expected_revision: serverRev,
                      current_revision: serverRev,
                      design: recovered,
                    },
                  },
                },
              )
        }
        return updateStudioDraft(recovered.id, cloudDoc, {
          expectedRevision: serverRev,
        })
      }
    } catch (reconcileErr) {
      if (parseDraftConflict(reconcileErr)) throw reconcileErr
      /* rethrow original create failure below */
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
  /** Last revision actually acknowledged by the server (not a speculative local rev). */
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
    // No cloud write — never invent a newer syncedRevision from the local document.
    if (args.expectedRevision == null) {
      return {
        ok: false,
        conflict: null,
        localPersisted,
        error: 'Missing server-acknowledged revision for unchanged draft fingerprint.',
        designId: args.designId,
      }
    }
    return {
      ok: true,
      designId: args.designId,
      document: cloudDoc,
      fingerprint: cloudFingerprint,
      syncedRevision: args.expectedRevision,
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
    const acknowledgedFingerprint = draftContentFingerprint(documentForCloud(extracted))
    // Create/reconcile may return an existing draft that was not overwritten.
    // Never report success when that copy differs from the document we sent.
    if (acknowledgedFingerprint !== cloudFingerprint) {
      return {
        ok: false,
        conflict: {
          local: args.document,
          server: extracted,
          designId: saved.id,
        },
        localPersisted,
        error:
          'Server draft content differs from this device. Choose which copy to keep.',
      }
    }
    // Monotonic: must not overwrite a newer local recovery doc with this (possibly stale) save.
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
      fingerprint: acknowledgedFingerprint,
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

/** Explicit Keep-this-device: rebase above the seen server revision, then OCC save. */
export async function commitKeepDeviceChoice(args: {
  userId: string
  designId: string
  local: StudioDraftDocument
  serverRevision: number
}): Promise<PersistResult> {
  const rebased = rebaseChosenLocalDraft(args.local, args.serverRevision)
  return persistStudioDraft({
    userId: args.userId,
    designId: args.designId,
    document: rebased,
    fingerprint: draftContentFingerprint(documentForCloud(rebased)),
    lastSyncedFingerprint: null,
    expectedRevision: args.serverRevision,
  })
}

/**
 * Explicit Use-cloud: durably replace IndexedDB even if the cloud revision is lower.
 * Caller must not show Saved unless this returns ok.
 */
export async function commitUseCloudChoice(args: {
  userId: string
  designId: string
  server: StudioDraftDocument
}): Promise<{ ok: true } | { ok: false; error: string }> {
  const replaced = await replaceLocalDraft({
    userId: args.userId,
    designId: args.designId,
    document: args.server,
    savedAt: new Date().toISOString(),
    syncedRevision: args.server.clientRevision,
  })
  if (!replaced.ok) return { ok: false, error: replaced.error }
  writeStoredDesignId(args.userId, args.designId)
  return { ok: true }
}
