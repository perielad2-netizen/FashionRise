#!/usr/bin/env node
/**
 * Production build for Capacitor (App Store / Play Store).
 * Loads .env.native so the API base is absolute https://fashionrise.app/api/v1.
 */
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const envPath = path.join(root, '.env.native')

function loadEnvFile(file) {
  if (!fs.existsSync(file)) return {}
  const out = {}
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const t = line.trim()
    if (!t || t.startsWith('#')) continue
    const i = t.indexOf('=')
    if (i < 0) continue
    out[t.slice(0, i).trim()] = t.slice(i + 1).trim()
  }
  return out
}

const fromFile = loadEnvFile(envPath)
const env = {
  ...process.env,
  ...fromFile,
  VITE_NATIVE_SHELL: 'true',
  VITE_BUILD_SHA: process.env.VITE_BUILD_SHA || process.env.GITHUB_SHA || 'native',
}

if (!env.VITE_API_BASE_URL || env.VITE_API_BASE_URL.startsWith('/')) {
  console.error('build-native: VITE_API_BASE_URL must be absolute (see .env.native)')
  process.exit(1)
}

console.log('build-native: API=', env.VITE_API_BASE_URL)
const r = spawnSync('npm', ['run', 'build'], { cwd: root, env, stdio: 'inherit' })
process.exit(r.status ?? 1)
