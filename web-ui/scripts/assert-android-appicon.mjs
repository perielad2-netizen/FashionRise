#!/usr/bin/env node
/**
 * Fail closed if the Capacitor Android launcher icons are missing or blank.
 * Does not modify icons — only verifies committed mipmap assets look real.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const resRoot = path.join(root, 'android/app/src/main/res')
const densities = ['mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi']

function fail(msg) {
  console.error(`assert-android-appicon: FAIL — ${msg}`)
  process.exit(1)
}

function scanWithPython(pngPath) {
  const py = `
from PIL import Image
im = Image.open(${JSON.stringify(pngPath)}).convert("RGBA")
w, h = im.size
px = list(im.getdata())
n = len(px)
if n == 0:
    raise SystemExit("empty")
opaque = [p for p in px if p[3] > 8]
if len(opaque) < max(16, n // 50):
    raise SystemExit("too_transparent")
uniq = len({(p[0]//8, p[1]//8, p[2]//8) for p in opaque})
if uniq < 8:
    raise SystemExit(f"too_flat uniq={uniq}")
whiteish = sum(1 for p in opaque if p[0] > 245 and p[1] > 245 and p[2] > 245)
if whiteish / len(opaque) > 0.92:
    raise SystemExit("mostly_white")
print(f"ok size={w}x{h} opaque={len(opaque)} uniq~={uniq}")
`
  const pillow = spawnSync('python3', ['-c', 'import PIL'], { encoding: 'utf8' })
  if (pillow.status !== 0) {
    fail('Python Pillow required for Android icon pixel scan (pip install pillow)')
  }
  const r = spawnSync('python3', ['-c', py], { encoding: 'utf8' })
  if (r.status !== 0) {
    fail(`${pngPath}: pixel scan failed — ${(r.stderr || r.stdout || '').trim() || 'unknown'}`)
  }
  return (r.stdout || '').trim()
}

for (const d of densities) {
  const dir = path.join(resRoot, `mipmap-${d}`)
  const launcher = path.join(dir, 'ic_launcher.png')
  if (!fs.existsSync(launcher)) fail(`missing ${launcher}`)
  const st = fs.statSync(launcher)
  if (st.size < 800) fail(`${launcher} too small (${st.size} bytes) — likely placeholder`)
}

const sample = path.join(resRoot, 'mipmap-xxhdpi/ic_launcher.png')
const out = scanWithPython(sample)
console.log(`assert-android-appicon: ${out} (${sample})`)

const anydpi = path.join(resRoot, 'mipmap-anydpi-v26/ic_launcher.xml')
if (!fs.existsSync(anydpi)) fail(`missing ${anydpi}`)
const xml = fs.readFileSync(anydpi, 'utf8')
if (!xml.includes('ic_launcher_foreground')) {
  fail('ic_launcher.xml must reference ic_launcher_foreground')
}

console.log('assert-android-appicon: PASS')
