#!/usr/bin/env node
/**
 * Guard: FashionRise Android must not declare CAMERA.
 * Fitting Room uses system ACTION_IMAGE_CAPTURE via HTML capture= — declaring
 * CAMERA reintroduces the permission dialog / SecurityException crash path.
 */
import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const manifestPath = resolve(root, 'android/app/src/main/AndroidManifest.xml')
const xml = readFileSync(manifestPath, 'utf8')

const declaresCamera = /<uses-permission[^>]*android:name="android\.permission\.CAMERA"[^>]*>/g
const matches = [...xml.matchAll(declaresCamera)]
if (matches.length === 0) {
  console.error('FAIL: expected an explicit CAMERA tools:node="remove" entry in AndroidManifest.xml')
  process.exit(1)
}

for (const match of matches) {
  const tag = match[0]
  if (!/tools:node\s*=\s*"remove"/.test(tag)) {
    console.error('FAIL: CAMERA permission must use tools:node="remove" (found active declare):')
    console.error(tag)
    process.exit(1)
  }
}

// Optional: if a merged manifest from a local gradle run exists, ensure CAMERA is gone.
const mergedCandidates = [
  resolve(root, 'android/app/build/intermediates/merged_manifest/debug/processDebugMainManifest/AndroidManifest.xml'),
  resolve(root, 'android/app/build/intermediates/merged_manifests/debug/processDebugManifest/AndroidManifest.xml'),
  resolve(root, 'android/app/build/intermediates/merged_manifest/release/processReleaseMainManifest/AndroidManifest.xml'),
]
for (const merged of mergedCandidates) {
  if (!existsSync(merged)) continue
  const mergedXml = readFileSync(merged, 'utf8')
  if (/android\.permission\.CAMERA/.test(mergedXml)) {
    console.error(`FAIL: merged manifest still contains CAMERA: ${merged}`)
    process.exit(1)
  }
  console.log(`OK: merged manifest has no CAMERA (${merged})`)
}

console.log('OK: AndroidManifest CAMERA is tools:node="remove" only')
