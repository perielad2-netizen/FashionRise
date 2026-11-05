/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/vanillajs" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  /** When true, show Create Account and serve /register. Default off. */
  readonly VITE_REGISTRATION_UI_ENABLED?: string
  /** When true, enable Magic UX in Studio. Default off until activation. */
  readonly VITE_MAGIC_UI_ENABLED?: string
  /** When true, enable Front/Back Studio. Default off. */
  readonly VITE_STUDIO_FRONT_BACK_ENABLED?: string
  /** When true, allow Dual Magic (Front+Back polish). Default off. */
  readonly VITE_STUDIO_DUAL_MAGIC_ENABLED?: string
  /** When true, show Create My Croquis wizard. Default off (independent of #136 gates). */
  readonly VITE_MY_CROQUIS_UI_ENABLED?: string
  /** Owner/legal-approved adults notice body. Empty → consent fail-closed. */
  readonly VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT?: string
  /** Owner/legal-approved storage notice body. Empty → consent fail-closed. */
  readonly VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT?: string
  /** Owner/legal-approved AI notice body. Empty → consent fail-closed. */
  readonly VITE_MY_CROQUIS_AI_NOTICE_TEXT?: string
  /** Short git SHA injected at build time for App version badge. */
  readonly VITE_BUILD_SHA?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
