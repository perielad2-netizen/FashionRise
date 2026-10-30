/**
 * Incident #136 — fail production builds that silently drop already-approved
 * Studio gates (Front/Back, Magic UI, Dual Magic).
 *
 * Checks:
 * 1) Process env allowlist (booleans only) matches expected production gates.
 * 2) Compiled index bundle constant-folds `isStudioFrontBackEnabled` to true
 *    (`function <id>(){return!0}` via `frontBackEnabled??<id>()`).
 *
 * Does not print secrets. Safe to run in CI and `npm run build`.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(root, 'dist')
const assets = path.join(dist, 'assets')

/** Expected production FE gate allowlist (names + effective booleans only). */
export const EXPECTED_PROD_VITE_FLAGS = Object.freeze({
  VITE_API_BASE_URL: '/api/v1',
  VITE_MAGIC_UI_ENABLED: true,
  VITE_STUDIO_FRONT_BACK_ENABLED: true,
  VITE_STUDIO_DUAL_MAGIC_ENABLED: true,
})

function parseBool(raw) {
  const v = (raw ?? '').trim().toLowerCase()
  return v === '1' || v === 'true' || v === 'yes' || v === 'on'
}

function envBool(name) {
  return parseBool(process.env[name])
}

function fail(msg) {
  console.error(`assert-prod-vite-flags: ${msg}`)
  process.exit(1)
}

// --- 1) Build-time env allowlist ---
const apiBase = (process.env.VITE_API_BASE_URL ?? '').trim()
if (apiBase !== EXPECTED_PROD_VITE_FLAGS.VITE_API_BASE_URL) {
  fail(
    `VITE_API_BASE_URL expected ${EXPECTED_PROD_VITE_FLAGS.VITE_API_BASE_URL}, got ${JSON.stringify(apiBase) || '(empty)'}`,
  )
}

for (const name of [
  'VITE_MAGIC_UI_ENABLED',
  'VITE_STUDIO_FRONT_BACK_ENABLED',
  'VITE_STUDIO_DUAL_MAGIC_ENABLED',
]) {
  const expected = EXPECTED_PROD_VITE_FLAGS[name]
  const actual = envBool(name)
  if (actual !== expected) {
    fail(
      `${name} expected ${expected}, got ${actual} ` +
        `(raw=${JSON.stringify(process.env[name] ?? '')}). ` +
        'Refusing to ship a build that would hide Front/Back or Magic (incident #136).',
    )
  }
}

// --- 2) Compiled bundle proof ---
if (!fs.existsSync(assets)) {
  fail('dist/assets missing — run after vite build')
}
const indexJs = fs.readdirSync(assets).find((n) => n.startsWith('index-') && n.endsWith('.js'))
if (!indexJs) fail('no index-*.js in dist/assets')
const text = fs.readFileSync(path.join(assets, indexJs), 'utf8')

const helperMatch = text.match(/frontBackEnabled\?\?([A-Za-z0-9$]+)\(\)/)
if (!helperMatch) {
  fail('could not locate frontBackEnabled??<helper>() in bundle')
}
const helper = helperMatch[1]
const trueDef = new RegExp(`function ${helper}\\(\\)\\{return!0\\}`)
const falseDef = new RegExp(`function ${helper}\\(\\)\\{return!1\\}`)
if (falseDef.test(text)) {
  fail(
    `compiled isStudioFrontBackEnabled helper ${helper}() returns false (!1). ` +
      'VITE_STUDIO_FRONT_BACK_ENABLED was not true at build time.',
  )
}
if (!trueDef.test(text)) {
  fail(`compiled helper ${helper}() was not constant-folded to return!0`)
}

// Write BUILD_ENV.txt into dist for release forensics (booleans / routes only).
const buildEnvLines = [
  `VITE_API_BASE_URL=${apiBase}`,
  `VITE_REGISTRATION_UI_ENABLED=${envBool('VITE_REGISTRATION_UI_ENABLED')}`,
  `VITE_MAGIC_UI_ENABLED=${envBool('VITE_MAGIC_UI_ENABLED')}`,
  `VITE_STUDIO_FRONT_BACK_ENABLED=${envBool('VITE_STUDIO_FRONT_BACK_ENABLED')}`,
  `VITE_STUDIO_DUAL_MAGIC_ENABLED=${envBool('VITE_STUDIO_DUAL_MAGIC_ENABLED')}`,
  `VITE_BUILD_SHA=${(process.env.VITE_BUILD_SHA ?? '').trim()}`,
  `BUILT_AT_UTC=${new Date().toISOString()}`,
  `ASSERT_PROD_VITE_FLAGS=pass`,
]
fs.writeFileSync(path.join(dist, 'BUILD_ENV.txt'), `${buildEnvLines.join('\n')}\n`)

console.log(
  'assert-prod-vite-flags: ok ' +
    `(frontBack helper ${helper}=>true; magic=true; dualMagic=true; api=/api/v1)`,
)
