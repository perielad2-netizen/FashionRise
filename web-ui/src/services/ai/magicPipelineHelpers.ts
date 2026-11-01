import { fetchJobImageBlob } from '@/services/ai/magicApi'
import { toMagicLookResult, type MagicLookResult } from '@/services/ai/aiJobTypes'
import { pollAiJobUntilSettled } from '@/services/ai/pollAiJob'

export type SettledMagicSide = {
  jobId: string
  look: MagicLookResult
  lookObjectUrl: string | null
}

export async function settleMagicJobWithImage(
  jobId: string,
  signal?: AbortSignal,
): Promise<SettledMagicSide> {
  const settled = await pollAiJobUntilSettled({ jobId, signal })
  const look = toMagicLookResult(settled)
  let lookObjectUrl: string | null = null
  if (look.status !== 'failed' && look.hasImage) {
    const blob = await fetchJobImageBlob(settled.id, signal)
    lookObjectUrl = URL.createObjectURL(blob)
  }
  return { jobId: settled.id, look, lookObjectUrl }
}
