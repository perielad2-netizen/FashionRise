/**
 * Fail production builds that accidentally bake a developer API base
 * (e.g. http://127.0.0.1:8001/api/v1 from web-ui/.env). Phones then show
 * "Unable to reach FashionRise" because they cannot reach the developer's laptop.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(root, 'dist')
const assets = path.join(dist, 'assets')

if (!fs.existsSync(assets)) {
  console.error('assert-prod-api-base: dist/assets missing')
  process.exit(1)
}

const forbidden = [/https?:\/\/127\.0\.0\.1(?::\d+)?\/api\/v1/, /https?:\/\/localhost(?::\d+)?\/api\/v1/]
let found = null
for (const name of fs.readdirSync(assets)) {
  if (!name.endsWith('.js')) continue
  const text = fs.readFileSync(path.join(assets, name), 'utf8')
  for (const re of forbidden) {
    const m = text.match(re)
    if (m) {
      found = { file: name, match: m[0] }
      break
    }
  }
  if (found) break
}

if (found) {
  console.error(
    `assert-prod-api-base: forbidden API base ${found.match} in ${found.file}. ` +
      'Build with VITE_API_BASE_URL=/api/v1 (see .env.production).',
  )
  process.exit(1)
}

const indexJs = fs.readdirSync(assets).find((n) => n.startsWith('index-') && n.endsWith('.js'))
if (!indexJs) {
  console.error('assert-prod-api-base: no index-*.js')
  process.exit(1)
}
const text = fs.readFileSync(path.join(assets, indexJs), 'utf8')
if (!text.includes('`/api/v1`') && !text.includes('"/api/v1"') && !text.includes("'/api/v1'")) {
  // Accept relative /api/v1 only for same-origin production.
  console.error('assert-prod-api-base: expected relative /api/v1 in bundle')
  process.exit(1)
}

console.log('assert-prod-api-base: ok (/api/v1, no localhost)')
