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
  isStudioWorkingDraftClaim,
  listMyDesigns,
  parseDraftConflict,
  pickLatestStudioDraft,
  studioDraftRevisionHint,
  updateStudioDraft,
  type DesignRead,
} from '@/services/designsApi'
import { ApiError } from '@/services/api/client'

export { documentFromEditorState, rebaseChosenLocalDraft }

/** Present cloud Studio row that claims draft schema but fails strict parse. */
export type DamagedCloudDraft = {
  designId: string
  /** Original server row — never rewritten automatically. */
  rawDesign: DesignRead
  /** OCC hint from raw design_data / metadata when parse fails. */
  expectedRevision: number | null
  /** Existing IndexedDB recovery document (not overwritten by restore). */
  local: StudioDraftDocument | null
  hasLocalRecovery: boolean
}

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
  /** Set when cloud Studio draft exists but cannot be read safely. */
  damagedCloud: DamagedCloudDraft | null
  /**
   * When true, callers must not auto flushCloudSave / PUT / POST until the operator
   * explicitly recovers (keeps damaged cloud bytes intact).
   */
  blockAutomaticCloudWrites: boolean
  notice: string | null
}

const DAMAGED_CLOUD_NOTICE =
  'Your private cloud Studio draft could not be read (damaged or unsupported Front/Back data). The cloud copy was left unchanged. Automatic sync is paused until you choose recovery.'

function damagedCloudRestore(
  design: DesignRead,
  local: Awaited<ReturnType<typeof readLocalDraft>>,
  noticeExtra: string | null = null,
): RestoreResult {
  const localDoc = local?.document ?? null
  const notice = noticeExtra ? `${DAMAGED_CLOUD_NOTICE} ${noticeExtra}` : DAMAGED_CLOUD_NOTICE
  return {
    designId: design.id,
    // Prefer preserved local recovery for the canvas; never invent a sync from empty.
    document: localDoc ?? createEmptyDraftDocument(),
    syncedRevision: null,
    conflict: null,
    damagedCloud: {
      designId: design.id,
      rawDesign: design,
      expectedRevision: studioDraftRevisionHint(design),
      local: localDoc,
      hasLocalRecovery: Boolean(localDoc),
    },
    blockAutomaticCloudWrites: true,
    notice: withCustomRefNotice(localDoc ?? createEmptyDraftDocument(), notice),
  }
}

function cleanRestore(partial: Omit<RestoreResult, 'damagedCloud' | 'blockAutomaticCloudWrites'>): RestoreResult {
  return {
    ...partial,
    damagedCloud: null,
    blockAutomaticCloudWrites: false,
  }
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

function conflictWithExistingDraft(
  existing: DesignRead,
  message: string,
  expectedRevision: number,
): ApiError {
  return new ApiError(message, 409, {
    detail: {
      code: 'conflict',
      message,
      payload: {
        expected_revision: expectedRevision,
        current_revision: expectedRevision,
        design: existing,
      },
    },
  })
}

function sameCloudContent(a: StudioDraftDocument, b: StudioDraftDocument): boolean {
  return draftContentFingerprint(documentForCloud(a)) === draftContentFingerprint(documentForCloud(b))
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
        serverDesignId = design.id
        if (isStudioWorkingDraftClaim(design)) {
          serverDoc = extractStudioDraft(design)
          if (!serverDoc) {
            // Present-but-unreadable Studio V2/V1 row — do not fall through to empty/stale sync.
            writeStoredDesignId(userId, design.id)
            return damagedCloudRestore(design, local)
          }
        } else {
          serverDoc = extractStudioDraft(design)
        }
      } catch {
        serverDesignId = null
      }
    }

    if (!serverDoc) {
      const mine = await listMyDesigns()
      const latest = pickLatestStudioDraft(mine)
      if (latest) {
        serverDesignId = latest.id
        if (isStudioWorkingDraftClaim(latest)) {
          serverDoc = extractStudioDraft(latest)
          if (!serverDoc) {
            writeStoredDesignId(userId, latest.id)
            return damagedCloudRestore(latest, local)
          }
        } else {
          serverDoc = extractStudioDraft(latest)
        }
        if (serverDoc) writeStoredDesignId(userId, latest.id)
      }
    }
  } catch {
    notice = 'Working offline from this device. Changes save locally until the API is reachable.'
    if (local?.document) {
      return cleanRestore({
        designId: local.designId,
        document: local.document,
        syncedRevision: local.syncedRevision,
        conflict: null,
        notice: withCustomRefNotice(local.document, notice),
      })
    }
    return cleanRestore({
      designId: null,
      document: createEmptyDraftDocument(),
      syncedRevision: null,
      conflict: null,
      notice,
    })
  }

  if (local?.document && serverDoc && serverDesignId) {
    const decision = resolveDraftConflict(local.document, serverDoc)
    if (decision.needsUserChoice) {
      return cleanRestore({
        designId: serverDesignId,
        document: local.document,
        syncedRevision: local.syncedRevision ?? serverDoc.clientRevision,
        conflict: { local: local.document, server: serverDoc, designId: serverDesignId },
        notice: withCustomRefNotice(local.document, null),
      })
    }
    // Content equal — prefer server snapshot for synced revision tracking.
    return cleanRestore({
      designId: serverDesignId,
      document: serverDoc,
      syncedRevision: serverDoc.clientRevision,
      conflict: null,
      notice: withCustomRefNotice(serverDoc, null),
    })
  }

  if (serverDoc && serverDesignId) {
    return cleanRestore({
      designId: serverDesignId,
      document: serverDoc,
      syncedRevision: serverDoc.clientRevision,
      conflict: null,
      notice: withCustomRefNotice(serverDoc, null),
    })
  }

  if (local?.document) {
    return cleanRestore({
      designId: local.designId,
      document: local.document,
      syncedRevision: local.syncedRevision,
      conflict: null,
      notice: withCustomRefNotice(
        local.document,
        notice ?? 'Restored local recovery draft. Syncing to your private design…',
      ),
    })
  }

  return cleanRestore({
    designId: null,
    document: createEmptyDraftDocument(),
    syncedRevision: null,
    conflict: null,
    notice: null,
  })
}

/**
 * Explicit operator recovery: replace an unreadable cloud Studio draft with this device's
 * valid document. Never called automatically from restore/boot.
 */
export async function commitReplaceDamagedCloudDraft(args: {
  userId: string
  designId: string
  local: StudioDraftDocument
  expectedRevision: number
}): Promise<PersistResult> {
  const rebased = rebaseChosenLocalDraft(args.local, args.expectedRevision)
  return persistStudioDraft({
    userId: args.userId,
    designId: args.designId,
    document: rebased,
    fingerprint: draftContentFingerprint(documentForCloud(rebased)),
    lastSyncedFingerprint: null,
    expectedRevision: args.expectedRevision,
  })
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
 *
 * When `createOnly` is true (reopen into an empty Studio with no known draft id), never
 * adopt or overwrite another device's draft: same-content rows are recovered as a lost
 * response; anything else becomes a conflict for the caller to resolve explicitly.
 */
export async function ensureStudioDraft(
  userId: string,
  document: StudioDraftDocument,
  preferredDesignId: string | null,
  expectedRevision: number | null,
  options: { createOnly?: boolean } = {},
): Promise<DesignRead> {
  // Content compares use the serialized cloud shape. Wire create/update with the
  // original document so transient clearBackIntent still reaches metadata
  // (documentForCloud strips it — passing cloudDoc alone caused false 409s).
  const cloudDoc = documentForCloud(document)
  const createOnly = Boolean(options.createOnly)

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
      return await updateStudioDraft(preferredDesignId, document, {
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
    const serverDoc = extractStudioDraft(existing)
    const serverRev = serverDoc?.clientRevision
    if (serverRev == null || !serverDoc) {
      throw new ApiError('Studio draft is missing a server revision.', 409, null)
    }
    if (sameCloudContent(serverDoc, cloudDoc)) {
      writeStoredDesignId(userId, existing.id)
      return existing
    }
    if (createOnly) {
      throw conflictWithExistingDraft(
        existing,
        'Your working draft was created on another device.',
        serverRev,
      )
    }
    writeStoredDesignId(userId, existing.id)
    return updateStudioDraft(existing.id, document, {
      expectedRevision: serverRev,
    })
  }

  try {
    const created = await createStudioDraft(document)
    writeStoredDesignId(userId, created.id)
    return created
  } catch (createErr) {
    // Response may have been lost after a successful create — reconcile carefully.
    if (parseDraftConflict(createErr)) throw createErr
    try {
      const mine = await listMyDesigns()
      const recovered = pickLatestStudioDraft(mine)
      if (recovered) {
        const serverDoc = extractStudioDraft(recovered)
        if (!serverDoc) throw createErr
        const serverRev = serverDoc.clientRevision
        if (sameCloudContent(serverDoc, cloudDoc)) {
          writeStoredDesignId(userId, recovered.id)
          return recovered
        }
        if (createOnly) {
          throw conflictWithExistingDraft(
            recovered,
            'Your working draft was created on another device.',
            serverRev,
          )
        }
        writeStoredDesignId(userId, recovered.id)
        // Only advance when our content is a strict newer revision; otherwise surface conflict.
        if (cloudDoc.clientRevision < serverRev) {
          return recovered
        }
        if (cloudDoc.clientRevision === serverRev) {
          throw createErr instanceof ApiError
            ? createErr
            : conflictWithExistingDraft(
                recovered,
                'Studio working draft already exists with different content at this revision.',
                serverRev,
              )
        }
        return updateStudioDraft(recovered.id, document, {
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
  /**
   * Reopen-into-empty only: create the singleton draft, but never adopt/overwrite a
   * draft that appears from another device. Autosave must leave this unset.
   */
  createOnly?: boolean
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
    // Pass the original document (not cloudDoc) so clearBackIntent survives into
    // createStudioDraft / updateStudioDraft → cloudDraftMetadata.
    const saved = await ensureStudioDraft(
      args.userId,
      args.document,
      args.designId,
      args.expectedRevision,
      { createOnly: args.createOnly },
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
      // Lost-response / same-content 409: treat as ACK — never open a false conflict.
      if (sameCloudContent(serverDoc, cloudDoc)) {
        writeStoredDesignId(args.userId, conflictPayload.design.id)
        const localAfter = await writeLocalDraft({
          userId: args.userId,
          designId: conflictPayload.design.id,
          document: args.document,
          savedAt: new Date().toISOString(),
          syncedRevision: serverDoc.clientRevision,
        })
        return {
          ok: true,
          designId: conflictPayload.design.id,
          document: serverDoc,
          fingerprint: draftContentFingerprint(documentForCloud(serverDoc)),
          syncedRevision: serverDoc.clientRevision,
          localPersisted: localPersisted || localAfter.ok,
        }
      }
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
