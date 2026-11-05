/**
 * In-memory map of uploaded / AI fabric assetId → short Magic textile hint.
 * Populated when My Fabrics loads or an AI fabric is created.
 */

const promptByAsset = new Map<string, string>()

export function rememberFabricPromptShort(assetId: string, promptShort: string | null | undefined): void {
  const id = assetId.trim().toLowerCase()
  if (!id) return
  const text = (promptShort || '').trim()
  if (!text) {
    promptByAsset.delete(id)
    return
  }
  promptByAsset.set(id, text.slice(0, 160))
}

export function getFabricPromptShort(assetId: string): string | null {
  const id = assetId.trim().toLowerCase()
  if (!id) return null
  return promptByAsset.get(id) ?? null
}

export function clearFabricPromptCache(): void {
  promptByAsset.clear()
}

export function rememberFabricAssets(
  rows: Array<{ id: string; prompt_short?: string | null }>,
): void {
  for (const row of rows) {
    rememberFabricPromptShort(row.id, row.prompt_short)
  }
}
