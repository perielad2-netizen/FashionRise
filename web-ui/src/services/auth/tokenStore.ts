const ACCESS_KEY = 'fr.access_token'
const REFRESH_KEY = 'fr.refresh_token'

export type StoredTokens = {
  accessToken: string
  refreshToken: string
}

export const tokenStore = {
  get(): StoredTokens | null {
    const accessToken = localStorage.getItem(ACCESS_KEY)
    const refreshToken = localStorage.getItem(REFRESH_KEY)
    if (!accessToken || !refreshToken) return null
    return { accessToken, refreshToken }
  },

  set(tokens: StoredTokens): void {
    localStorage.setItem(ACCESS_KEY, tokens.accessToken)
    localStorage.setItem(REFRESH_KEY, tokens.refreshToken)
  },

  clear(): void {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}
