/**
 * Incident #136 — fail production builds that silently drop already-approved
 * Studio gates (Front/Back, Magic UI, Dual Magic) or accidentally enable
 * Registration UI.
 *
 * IMPORTANT: Vite may load `web-ui/.env.production` into `import.meta.env`
 * without exporting those keys into Node `process.env`. Env checks alone are
 * therefore insufficient. This script:
 *   1) Requires explicit Node env exports for the production allowlist
 *      (operators must `export VITE_*=…` for the build — do not rely on a
 *      gitignored `.env.production` being visible to this assert).
 *   2) Parses the compiled `dist/assets/index-*.js` and fail-closed proves
 *      all four gate helpers constant-folded to the expected booleans.
 *   3) Writes `BUILD_ENV.txt` + `COMPILED_GATES.json` (booleans only).
 *
 * Does not print secrets.
 */
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
  const bools = Object.fromEntries(
    [...bundleText.matchAll(/function ([A-Za-z0-9$]+)\(\)\{return(!0|!1)\}/g)].map((m) => [
      m[1],
      m[2] === '!0',
    ]),
  )

  const fbMatch = bundleText.match(/frontBackEnabled\?\?([A-Za-z0-9$]+)\(\)/)
  if (!fbMatch) {
    throw new Error('compiled bundle missing frontBackEnabled??<helper>()')
  }
  const frontBackId = fbMatch[1]

  const dualMatch = bundleText.match(
    new RegExp(`a=${frontBackId.replace(/\$/g, '\\$')}\\(\\),o=([A-Za-z0-9$]+)\\(\\)`),
  )
  if (!dualMatch) {
    throw new Error('compiled bundle missing dualMagic helper next to frontBack in Studio hook')
  }
  const dualId = dualMatch[1]

  const magicMatch = bundleText.match(/,Ze=([A-Za-z0-9$]+)\(\),Qe=/)
  if (!magicMatch) {
    throw new Error('compiled bundle missing magicUi helper (Ze=<helper>(),Qe= pattern)')
  }
  const magicId = magicMatch[1]

  const regMatch = bundleText.match(/path:`\/register`,element:([A-Za-z0-9$]+)\(\)\?/)
  if (!regMatch) {
    throw new Error('compiled bundle missing registration gate on /register route')
  }
  const regId = regMatch[1]

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

/** Fail-closed: compiled bundle must embed relative /api/v1 and must not embed localhost API bases. */
export function assertCompiledApiBase(bundleText) {
  const failures = []
  const hasRelative =
    bundleText.includes('`/api/v1`') ||
    bundleText.includes('"/api/v1"') ||
    bundleText.includes("'/api/v1'")
  if (!hasRelative) {
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
  if (apiBase !== expected.VITE_API_BASE_URL) {
    failures.push(
      `VITE_API_BASE_URL expected ${expected.VITE_API_BASE_URL}, got ${JSON.stringify(apiBase) || '(empty)'}`,
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

function fail(msg) {
  console.error(`assert-prod-vite-flags: ${msg}`)
  process.exit(1)
}

function main() {
  const envFailures = assertNodeEnvAllowlist()
  if (envFailures.length) fail(envFailures[0])

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

  const apiFailures = assertCompiledApiBase(text)
  if (apiFailures.length) fail(apiFailures.join('; '))

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
    `BUILT_AT_UTC=${new Date().toISOString()}`,
    `ASSERT_PROD_VITE_FLAGS=pass`,
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

  console.log(
    'assert-prod-vite-flags: ok ' +
      `(compiled frontBack=${gates.frontBack.value} magic=${gates.magicUi.value} ` +
      `dual=${gates.dualMagic.value} registration=${gates.registration.value}; api=/api/v1; sha=${buildSha.slice(0, 8)})`,
  )
}

const isMain =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) main()
