#!/usr/bin/env node
/**
 * Fail-closed check: generated dist/sw.js must not precache HTML or install a
 * Workbox navigation fallback. Used after `npm run build` and in unit tests.
 *
 * Usage:
 *   node scripts/assert-sw-access-safe.mjs [path/to/sw.js]
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { assertServiceWorkerAccessSafe, formatSwSafetyReport } from './swAccessSafety.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const swPath = path.resolve(process.argv[2] || path.join(here, '..', 'dist', 'sw.js'))

if (!fs.existsSync(swPath)) {
  console.error(`assert-sw-access-safe: missing ${swPath}`)
  console.error('Run `npm run build` first.')
  process.exit(2)
}

const source = fs.readFileSync(swPath, 'utf8')
const result = assertServiceWorkerAccessSafe(source)
console.log(formatSwSafetyReport(result, swPath))
if (!result.ok) {
  process.exit(1)
}
