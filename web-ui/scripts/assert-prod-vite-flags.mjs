/**
 * Incident #136 — fail production builds that silently drop already-approved
 * Studio gates (Front/Back, Magic UI, Dual Magic) or accidentally enable
 * Registration UI.
 *
 * Issue #158 — also fail builds that omit Create My Croquis consent notices.
 * Vite only replaces **static** `import.meta.env.VITE_*` access; dynamic
 * `import.meta.env[name]` ships empty and blocked the wizard in production.
 *
 * IMPORTANT: Vite may load `web-ui/.env.production` into `import.meta.env`
 * without exporting those keys into Node `process.env`. Env checks alone are
 * therefore insufficient. This script:
 *   1) Requires explicit Node env exports for the production allowlist
 *      (operators must `export VITE_*=…` for the build — do not rely on a
 *      gitignored `.env.production` being visible to this assert).
 *   2) Parses the compiled `dist/assets/index-*.js` and fail-closed proves
 *      all four gate helpers constant-folded to the expected booleans.
 *   3) Requires the three approved notice texts in Node env, verifies SHA256
 *      against the known production hashes (matching backend `.env`), and
 *      proves each notice string is embedded in the compiled bundle.
 *   4) Writes `BUILD_ENV.txt` + `COMPILED_GATES.json` + `COMPILED_NOTICES.json`
 *      (hashes/lengths/versions only — never notice bodies).
 *
 * Does not print secrets / notice bodies.
 */
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(root, 'dist')
const assets = path.join(dist, 'assets')

/**
 * Expected production FE gate allowlist (names + effective booleans only).
 * Sourced from known-good immutable release BUILD_ENV.txt (`69b83c01`,
 * `af1ddbb5`, `31c1de01`) — not invented from `.env.production.example`.
 */
export const EXPECTED_PROD_VITE_FLAGS = Object.freeze({
  VITE_API_BASE_URL: '/api/v1',
  VITE_REGISTRATION_UI_ENABLED: false,
  VITE_MAGIC_UI_ENABLED: true,
  VITE_STUDIO_FRONT_BACK_ENABLED: true,
  VITE_STUDIO_DUAL_MAGIC_ENABLED: true,
})

/** Create My Croquis notice env keys (must be static `import.meta.env` access). */
export const CROQUIS_NOTICE_ENV_KEYS = Object.freeze([
  'VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT',
  'VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT',
  'VITE_MY_CROQUIS_AI_NOTICE_TEXT',
])

/**
 * Approved production notice SHA256 digests (UTF-8) for adults-beta / storage /
 * ai-provider versions `2026-11-01`. Must match backend `MY_CROQUIS_*_NOTICE_TEXT`.
 * Override via `EXPECTED_MY_CROQUIS_*_NOTICE_SHA256` only when intentionally
 * rotating approved legal copy together with the backend.
 */
export const EXPECTED_PROD_NOTICE_SHA256 = Object.freeze({
  VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT:
    '882c9ed42b5f8b75d5b4e414732329ddd7daa0dfb537491bdded0428b6e41df9',
  VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT:
    '27882295bca4c06b61ea0cb729127345f006cb01b1b3c32ca5e986bc0838a589',
  VITE_MY_CROQUIS_AI_NOTICE_TEXT:
    'c3226ed38db0b86f3ab18377340c37ded733b0603bddae7c597a7b2aeea39cb8',
})

/** FE notice version constants — must stay aligned with backend attestation versions. */
export const EXPECTED_PROD_NOTICE_VERSIONS = Object.freeze({
  adults: 'adults-beta-2026-11-01',
  storage: 'storage-2026-11-01',
  ai: 'ai-provider-2026-11-01',
})

export function sha256Hex(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex')
}

export function sanitizeNoticeText(raw) {
  const text = (raw ?? '').trim()
  if (!text) return ''
  const lower = text.toLowerCase()
  if (lower.includes('draft') || lower.includes('placeholder') || lower.includes('todo')) {
    return ''
  }
  return text
}

export function parseBool(raw) {
  const v = (raw ?? '').trim().toLowerCase()
  return v === '1' || v === 'true' || v === 'yes' || v === 'on'
}

/** Effective Node-env boolean; registration unset/empty ⇒ false. */
export function effectiveEnvBool(name, env = process.env) {
  const raw = env[name]
  if (name === 'VITE_REGISTRATION_UI_ENABLED' && (raw == null || raw === '')) return false
  return parseBool(raw)
}

/**
 * Locate constant-folded gate helpers in a minified Studio bundle.
 * Returns { frontBack, dualMagic, magicUi, registration } helper ids + values.
 */
export function extractCompiledGates(bundleText) {
  // Identifiers may include `_` (Rolldown/esbuild often emits `_S`, `_t`, …).
  const ID = '[A-Za-z0-9$_]+'
  const bools = Object.fromEntries(
    [...bundleText.matchAll(new RegExp(`function (${ID})\\(\\)\\{return(!0|!1)\\}`, 'g'))].map(
      (m) => [m[1], m[2] === '!0'],
    ),
  )

  const fbMatch = bundleText.match(new RegExp(`frontBackEnabled\\?\\?(${ID})\\(\\)`))
  if (!fbMatch) {
    throw new Error('compiled bundle missing frontBackEnabled??<helper>()')
  }
  const frontBackId = fbMatch[1]

  // Minifier local names drift across Rolldown builds:
  // 1) Legacy: `a=<frontBack>(),o=<dualMagic>()`
  // 2) Current: `o=<frontBack>(),s=<dualMagic>()`
  const fbEsc = frontBackId.replace(/\$/g, '\\$')
  const dualMatch =
    bundleText.match(new RegExp(`a=${fbEsc}\\(\\),o=(${ID})\\(\\)`)) ||
    bundleText.match(new RegExp(`o=${fbEsc}\\(\\),s=(${ID})\\(\\)`))
  if (!dualMatch) {
    throw new Error('compiled bundle missing dualMagic helper next to frontBack in Studio hook')
  }
  const dualId = dualMatch[1]

  // Magic UI helper fingerprints (minifier renames locals across builds):
  // 1) Legacy Studio hook: `,Ze=<helper>(),Qe=`
  // 2) Current: `useRef)(!1),<local>=<helper>(),…===`capturing`` next to magic phase busy check
  const magicMatch =
    bundleText.match(new RegExp(`,Ze=(${ID})\\(\\),Qe=`)) ||
    bundleText.match(
      new RegExp(
        `useRef\\)\\(!1\\),(${ID})=(${ID})\\(\\),${ID}=${ID}===\`capturing\``,
      ),
    )
  if (!magicMatch) {
    throw new Error(
      'compiled bundle missing magicUi helper (legacy Ze=…,Qe= or useRef)(!1),…capturing pattern)',
    )
  }
  const magicId = magicMatch[2] || magicMatch[1]

  // Registration UI build flag (must stay false in production):
  // 1) Legacy: Vite ternary gate on /register → `path:`/register`,element:Ii()?…`
  // 2) Current: /register always mounts RegisterPage; key keeps helper live as
  //    `…(Oc,{},to()?`reg-on`:`reg-off`)` while backend status gates the UX.
  let regId = null
  const regRouteMatch = bundleText.match(
    new RegExp(`path:\`/register\`,element:(${ID})\\(\\)\\?`),
  )
  const regKeyMatch = bundleText.match(
    new RegExp(`path:\`/register\`[\\s\\S]{0,120}?(${ID})\\(\\)\\?\`reg-on\`:\`reg-off\``),
  )
  if (regRouteMatch) {
    regId = regRouteMatch[1]
  } else if (regKeyMatch) {
    regId = regKeyMatch[1]
  } else if (!bundleText.includes('path:`/register`') && !bundleText.includes('path:"/register"')) {
    throw new Error('compiled bundle missing /register route')
  } else {
    throw new Error(
      'compiled bundle missing registration gate helper (expected false-folded isRegistrationUiEnabled)',
    )
  }

  const requireBool = (id, label) => {
    if (!(id in bools)) {
      throw new Error(`compiled ${label} helper ${id}() was not constant-folded to !0/!1`)
    }
    return bools[id]
  }

  return {
    frontBack: { id: frontBackId, value: requireBool(frontBackId, 'frontBack') },
    dualMagic: { id: dualId, value: requireBool(dualId, 'dualMagic') },
    magicUi: { id: magicId, value: requireBool(magicId, 'magicUi') },
    registration: { id: regId, value: requireBool(regId, 'registration') },
  }
}

export function assertCompiledGatesMatchAllowlist(gates, expected = EXPECTED_PROD_VITE_FLAGS) {
  const checks = [
    ['VITE_STUDIO_FRONT_BACK_ENABLED', gates.frontBack, true],
    ['VITE_STUDIO_DUAL_MAGIC_ENABLED', gates.dualMagic, true],
    ['VITE_MAGIC_UI_ENABLED', gates.magicUi, true],
    ['VITE_REGISTRATION_UI_ENABLED', gates.registration, false],
  ]
  const failures = []
  for (const [name, gate, want] of checks) {
    if (expected[name] !== want) {
      // allowlist drift guard
      failures.push(`${name} allowlist expected constant ${want}`)
      continue
    }
    if (gate.value !== want) {
      failures.push(
        `compiled ${name} helper ${gate.id}() => ${gate.value}, expected ${want}`,
      )
    }
  }
  return failures
}

/** Fail-closed: compiled bundle must embed relative /api/v1 (web) or absolute fashionrise.app (native). */
export function assertCompiledApiBase(bundleText, env = process.env) {
  const failures = []
  const nativeShell = String(env.VITE_NATIVE_SHELL || '') === 'true'
  const hasRelative =
    bundleText.includes('`/api/v1`') ||
    bundleText.includes('"/api/v1"') ||
    bundleText.includes("'/api/v1'")
  const hasAbsoluteProd =
    bundleText.includes('https://fashionrise.app/api/v1') ||
    bundleText.includes('https://www.fashionrise.app/api/v1')
  if (nativeShell) {
    if (!hasAbsoluteProd) {
      failures.push('compiled native bundle missing https://fashionrise.app/api/v1')
    }
  } else if (!hasRelative) {
    failures.push('compiled bundle missing relative /api/v1')
  }
  if (/https?:\/\/127\.0\.0\.1(?::\d+)?\/api\/v1/.test(bundleText)) {
    failures.push('compiled bundle embeds http://127.0.0.1…/api/v1')
  }
  if (/https?:\/\/localhost(?::\d+)?\/api\/v1/.test(bundleText)) {
    failures.push('compiled bundle embeds http://localhost…/api/v1')
  }
  return failures
}

export function assertNodeEnvAllowlist(env = process.env, expected = EXPECTED_PROD_VITE_FLAGS) {
  const failures = []
  const apiBase = (env.VITE_API_BASE_URL ?? '').trim()
  const nativeShell = String(env.VITE_NATIVE_SHELL || '') === 'true'
  const apiOk = nativeShell
    ? apiBase === 'https://fashionrise.app/api/v1' || apiBase === 'https://www.fashionrise.app/api/v1'
    : apiBase === expected.VITE_API_BASE_URL
  if (!apiOk) {
    failures.push(
      nativeShell
        ? `VITE_API_BASE_URL expected https://fashionrise.app/api/v1 for native, got ${JSON.stringify(apiBase) || '(empty)'}`
        : `VITE_API_BASE_URL expected ${expected.VITE_API_BASE_URL}, got ${JSON.stringify(apiBase) || '(empty)'}`,
    )
  }
  for (const name of [
    'VITE_REGISTRATION_UI_ENABLED',
    'VITE_MAGIC_UI_ENABLED',
    'VITE_STUDIO_FRONT_BACK_ENABLED',
    'VITE_STUDIO_DUAL_MAGIC_ENABLED',
  ]) {
    const got = effectiveEnvBool(name, env)
    if (got !== expected[name]) {
      failures.push(
        `${name} expected ${expected[name]}, got ${got} (raw=${JSON.stringify(env[name] ?? '')}). ` +
          'Export VITE_* explicitly for production builds; do not rely on gitignored .env.production alone.',
      )
    }
  }
  return failures
}

/**
 * Fail-closed Create My Croquis notices (#158).
 * Returns { failures, notices } where notices maps env key → { text, sha256, length }.
 */
export function assertCroquisNoticeEnv(
  env = process.env,
  expectedSha = EXPECTED_PROD_NOTICE_SHA256,
) {
  const failures = []
  const notices = {}
  for (const name of CROQUIS_NOTICE_ENV_KEYS) {
    const sanitized = sanitizeNoticeText(env[name])
    if (!sanitized) {
      failures.push(
        `${name} missing or rejected (empty/draft/placeholder). ` +
          'Export approved notice text for production builds (#158).',
      )
      continue
    }
    const digest = sha256Hex(sanitized)
    const overrideKey = `EXPECTED_${name.replace(/^VITE_/, '')}_SHA256`
    const want = (env[overrideKey] || expectedSha[name] || '').trim().toLowerCase()
    if (want && digest !== want) {
      failures.push(
        `${name} SHA256 ${digest} does not match expected ${want} ` +
          '(frontend must match effective backend MY_CROQUIS_*_NOTICE_TEXT).',
      )
    }
    notices[name] = { sha256: digest, length: sanitized.length, text: sanitized }
  }
  return { failures, notices }
}

/** Prove Vite inlined each notice into the compiled Studio bundle. */
export function assertCompiledNoticesPresent(bundleText, notices) {
  const failures = []
  for (const [name, info] of Object.entries(notices)) {
    if (!info?.text) {
      failures.push(`${name} has no sanitized text to search for in bundle`)
      continue
    }
    if (!bundleText.includes(info.text)) {
      failures.push(
        `compiled bundle missing ${name} body (Vite did not inline static import.meta.env — #158 regression)`,
      )
    }
  }
  return failures
}

function fail(msg) {
  console.error(`assert-prod-vite-flags: ${msg}`)
  process.exit(1)
}

function main() {
  const envFailures = assertNodeEnvAllowlist()
  if (envFailures.length) fail(envFailures[0])

  const { failures: noticeEnvFailures, notices } = assertCroquisNoticeEnv()
  if (noticeEnvFailures.length) fail(noticeEnvFailures[0])

  if (!fs.existsSync(assets)) fail('dist/assets missing — run after vite build')
  const indexJs = fs.readdirSync(assets).find((n) => n.startsWith('index-') && n.endsWith('.js'))
  if (!indexJs) fail('no index-*.js in dist/assets')
  const text = fs.readFileSync(path.join(assets, indexJs), 'utf8')

  let gates
  try {
    gates = extractCompiledGates(text)
  } catch (err) {
    fail(err instanceof Error ? err.message : String(err))
  }

  const compiledFailures = assertCompiledGatesMatchAllowlist(gates)
  if (compiledFailures.length) fail(compiledFailures.join('; '))

  const apiFailures = assertCompiledApiBase(text, process.env)
  if (apiFailures.length) fail(apiFailures.join('; '))

  const noticeBundleFailures = assertCompiledNoticesPresent(text, notices)
  if (noticeBundleFailures.length) fail(noticeBundleFailures.join('; '))

  const apiBase = (process.env.VITE_API_BASE_URL ?? '').trim()
  const buildSha = (process.env.VITE_BUILD_SHA ?? '').trim()
  if (!buildSha) {
    fail('VITE_BUILD_SHA must be set to the final PR #137 tip SHA (new release identity; never reuse 6ec73ba2)')
  }
  if (/^6ec73ba2/i.test(buildSha)) {
    fail(
      'VITE_BUILD_SHA must not be the defective 6ec73ba2 release identity — use the final reviewed PR #137 tip SHA',
    )
  }

  const buildEnvLines = [
    `VITE_API_BASE_URL=${apiBase}`,
    `VITE_REGISTRATION_UI_ENABLED=${effectiveEnvBool('VITE_REGISTRATION_UI_ENABLED')}`,
    `VITE_MAGIC_UI_ENABLED=${effectiveEnvBool('VITE_MAGIC_UI_ENABLED')}`,
    `VITE_STUDIO_FRONT_BACK_ENABLED=${effectiveEnvBool('VITE_STUDIO_FRONT_BACK_ENABLED')}`,
    `VITE_STUDIO_DUAL_MAGIC_ENABLED=${effectiveEnvBool('VITE_STUDIO_DUAL_MAGIC_ENABLED')}`,
    `VITE_BUILD_SHA=${buildSha}`,
    `CROQUIS_ADULTS_NOTICE_VERSION=${EXPECTED_PROD_NOTICE_VERSIONS.adults}`,
    `CROQUIS_STORAGE_NOTICE_VERSION=${EXPECTED_PROD_NOTICE_VERSIONS.storage}`,
    `CROQUIS_AI_NOTICE_VERSION=${EXPECTED_PROD_NOTICE_VERSIONS.ai}`,
    `CROQUIS_ADULTS_NOTICE_SHA256=${notices.VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT.sha256}`,
    `CROQUIS_STORAGE_NOTICE_SHA256=${notices.VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT.sha256}`,
    `CROQUIS_AI_NOTICE_SHA256=${notices.VITE_MY_CROQUIS_AI_NOTICE_TEXT.sha256}`,
    `BUILT_AT_UTC=${new Date().toISOString()}`,
    `ASSERT_PROD_VITE_FLAGS=pass`,
    `ASSERT_PROD_CROQUIS_NOTICES=pass`,
  ]
  fs.writeFileSync(path.join(dist, 'BUILD_ENV.txt'), `${buildEnvLines.join('\n')}\n`)

  const compiledManifest = {
    frontBack: gates.frontBack.value,
    dualMagic: gates.dualMagic.value,
    magicUi: gates.magicUi.value,
    registration: gates.registration.value,
    apiBase: '/api/v1',
    buildSha,
    helpers: {
      frontBack: gates.frontBack.id,
      dualMagic: gates.dualMagic.id,
      magicUi: gates.magicUi.id,
      registration: gates.registration.id,
    },
    source: indexJs,
  }
  fs.writeFileSync(path.join(dist, 'COMPILED_GATES.json'), `${JSON.stringify(compiledManifest, null, 2)}\n`)

  const noticeManifest = {
    versions: EXPECTED_PROD_NOTICE_VERSIONS,
    notices: Object.fromEntries(
      Object.entries(notices).map(([name, info]) => [
        name,
        { sha256: info.sha256, length: info.length, embedded: true },
      ]),
    ),
    source: indexJs,
    buildSha,
  }
  fs.writeFileSync(path.join(dist, 'COMPILED_NOTICES.json'), `${JSON.stringify(noticeManifest, null, 2)}\n`)

  console.log(
    'assert-prod-vite-flags: ok ' +
      `(compiled frontBack=${gates.frontBack.value} magic=${gates.magicUi.value} ` +
      `dual=${gates.dualMagic.value} registration=${gates.registration.value}; api=/api/v1; ` +
      `notices=pass; sha=${buildSha.slice(0, 8)})`,
  )
}

const isMain =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) main()
