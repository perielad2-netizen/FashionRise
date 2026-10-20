/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  /** When true, show Create Account and serve /register. Default off. */
  readonly VITE_REGISTRATION_UI_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
