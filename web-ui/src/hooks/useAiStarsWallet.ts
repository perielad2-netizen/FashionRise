import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@/services/auth/AuthProvider'
import {
  fetchStarsWallet,
  type StarsWallet,
} from '@/services/starsShopApi'

/** Defaults match backend AI_STARS_*_COST env used in production. */
export const DEFAULT_AI_STAR_COSTS = Object.freeze({
  magic: 10,
  croquis: 10,
  pdf: 50,
  fabric: 5,
})

export type AiStarCosts = typeof DEFAULT_AI_STAR_COSTS

/**
 * Live Stars balance from auth, plus feature costs from `/auth/stars`
 * (falls back to known production defaults while loading).
 */
export function useAiStarsWallet() {
  const { user, refreshUser } = useAuth()
  const unlimited = Boolean(user?.ai_stars_unlimited)
  const balance = unlimited ? null : Number(user?.ai_stars ?? 0)
  const [costs, setCosts] = useState<AiStarCosts>({ ...DEFAULT_AI_STAR_COSTS })
  const [loaded, setLoaded] = useState(false)

  const reload = useCallback(async () => {
    try {
      const wallet: StarsWallet = await fetchStarsWallet()
      setCosts({
        magic: wallet.ai_stars_costs?.magic ?? DEFAULT_AI_STAR_COSTS.magic,
        croquis: wallet.ai_stars_costs?.croquis ?? DEFAULT_AI_STAR_COSTS.croquis,
        pdf: wallet.ai_stars_costs?.pdf ?? DEFAULT_AI_STAR_COSTS.pdf,
        fabric: wallet.ai_stars_costs?.fabric ?? DEFAULT_AI_STAR_COSTS.fabric,
      })
      void refreshUser()
    } catch {
      /* keep defaults — spend confirm still shows a cost */
    } finally {
      setLoaded(true)
    }
  }, [refreshUser])

  useEffect(() => {
    void reload()
  }, [reload])

  return {
    balance,
    unlimited,
    costs,
    loaded,
    reload,
    refreshUser,
  }
}
