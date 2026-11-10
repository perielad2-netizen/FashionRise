#!/usr/bin/env node
/**
 * Fail closed if the Capacitor iOS AppIcon asset is missing, wrong size/mode,
 * or blank (all-white). A white 1024 PNG looks like a "placeholder" on Apple's
 * purchase sheet even though Xcode builds succeed.
 *
 * Pixel validation requires one of: sharp, @napi-rs/canvas (web-ui
 * devDependency — present after `npm ci`), or Python Pillow. There is no
 * size-only success path — missing scanners fail the build.
 *
 * Env overrides (tests / fixtures only — do not use in release builds):
 *   FR_IOS_APPICON_PNG  — absolute path to a PNG to pixel-scan instead of the
 *                         committed AppIcon-512@2x.png (project wiring still
 *                         checked against the real ios/ tree unless
 *                         FR_IOS_APPICON_SKIP_PROJECT=1).
 *   FR_IOS_APPICON_SKIP_PROJECT=1 — skip pbxproj/Contents.json checks (fixture).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { spawnSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultIconPath = path.join(
  root,
  'ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png',
)
const contentsPath = path.join(
  root,
  'ios/App/App/Assets.xcassets/AppIcon.appiconset/Contents.json',
)
const pbxproj = path.join(root, 'ios/App/App.xcodeproj/project.pbxproj')

const iconPath = (process.env.FR_IOS_APPICON_PNG || '').trim() || defaultIconPath
const skipProject = process.env.FR_IOS_APPICON_SKIP_PROJECT === '1'

function fail(msg) {
  console.error(`assert-ios-appicon: FAIL — ${msg}`)
  process.exit(1)
}

function assertProjectWiring() {
  if (!fs.existsSync(contentsPath)) fail(`missing ${contentsPath}`)
  if (!fs.existsSync(pbxproj)) fail(`missing ${pbxproj}`)

  const pbx = fs.readFileSync(pbxproj, 'utf8')
  if (!pbx.includes('ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon')) {
    fail('pbxproj missing ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon')
  }
  if (!pbx.includes('Assets.xcassets in Resources')) {
    fail('pbxproj does not copy Assets.xcassets into Resources')
  }

  const contents = JSON.parse(fs.readFileSync(contentsPath, 'utf8'))
  const images = contents.images || []
  if (!images.some((img) => img.filename === 'AppIcon-512@2x.png' && img.size === '1024x1024')) {
    fail('Contents.json must reference AppIcon-512@2x.png at 1024x1024')
  }
}

function nonWhitePctFromRgba(data, width, height) {
  let nonWhite = 0
  let hasTransparent = false
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    const a = data[i + 3]
    if (a < 255) hasTransparent = true
    if (!(r > 250 && g > 250 && b > 250)) nonWhite += 1
  }
  if (hasTransparent) fail('AppIcon must not have alpha (App Store rejects transparency)')
  return (100 * nonWhite) / (width * height)
}

/**
 * @param {string} pngPath
 * @param {Buffer} buf
 * @param {ReturnType<typeof createRequire>} require
 * @returns {Promise<{ width: number, height: number, nonWhitePct: number, via: string } | null>}
 */
async function trySharp(pngPath, buf, require) {
  let sharp
  try {
    sharp = require('sharp')
  } catch {
    return null
  }
  const meta = await sharp(buf).metadata()
  if (meta.width !== 1024 || meta.height !== 1024) {
    fail(`AppIcon must be 1024x1024, got ${meta.width}x${meta.height}`)
  }
  if (meta.hasAlpha) fail('AppIcon must not have alpha (App Store rejects transparency)')
  const { data, info } = await sharp(buf).raw().toBuffer({ resolveWithObject: true })
  let nonWhite = 0
  const channels = info.channels
  for (let i = 0; i < data.length; i += channels) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    if (!(r > 250 && g > 250 && b > 250)) nonWhite += 1
  }
  const nonWhitePct = (100 * nonWhite) / (info.width * info.height)
  return { width: info.width, height: info.height, nonWhitePct, via: 'sharp' }
}

/**
 * Prefer @napi-rs/canvas — already a web-ui devDependency, installed by Codemagic `npm ci`.
 * @param {string} pngPath
 * @param {ReturnType<typeof createRequire>} require
 * @returns {Promise<{ width: number, height: number, nonWhitePct: number, via: string } | null>}
 */
async function tryNapiCanvas(pngPath, require) {
  let canvas
  try {
    canvas = require('@napi-rs/canvas')
  } catch {
    return null
  }
  const img = await canvas.loadImage(pngPath)
  const width = img.width
  const height = img.height
  if (width !== 1024 || height !== 1024) {
    fail(`AppIcon must be 1024x1024, got ${width}x${height}`)
  }
  const c = canvas.createCanvas(width, height)
  const ctx = c.getContext('2d')
  ctx.drawImage(img, 0, 0)
  const { data } = ctx.getImageData(0, 0, width, height)
  const nonWhitePct = nonWhitePctFromRgba(data, width, height)
  return { width, height, nonWhitePct, via: 'napi-canvas' }
}

/**
 * @param {string} pngPath
 * @returns {{ width: number, height: number, nonWhitePct: number, via: string } | null}
 */
function tryPillow(pngPath) {
  const py = spawnSync(
    'python3',
    [
      '-c',
      `
from PIL import Image
import sys
path = sys.argv[1]
im = Image.open(path)
if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
    bands = im.getbands()
    if "A" in bands:
        extrema = im.getchannel("A").getextrema()
        if extrema[0] < 255:
            print("has_alpha", extrema, file=sys.stderr)
            raise SystemExit(3)
im = im.convert("RGB")
w, h = im.size
if (w, h) != (1024, 1024):
    print(f"size={w}x{h}", file=sys.stderr)
    raise SystemExit(4)
nw = sum(1 for p in im.getdata() if not (p[0] > 250 and p[1] > 250 and p[2] > 250))
pct = 100.0 * nw / (w * h)
print(f"{w} {h} {pct:.4f}")
`,
      pngPath,
    ],
    { encoding: 'utf8' },
  )

  if (py.error) return null
  if (py.status === 3) fail('AppIcon must not have alpha (App Store rejects transparency)')
  if (py.status === 4) fail(`AppIcon must be 1024x1024 (${(py.stderr || '').trim()})`)
  if (py.status !== 0) {
    // ModuleNotFoundError etc. — try next / fail closed at end
    const err = (py.stderr || py.stdout || '').trim()
    if (/No module named ['"]PIL['"]/i.test(err) || /ModuleNotFoundError/i.test(err)) {
      return null
    }
    fail(
      `Pillow pixel scan failed (exit ${py.status}). Install @napi-rs/canvas, sharp, or Pillow — size-only checks are not accepted. ${err}`,
    )
  }
  const parts = (py.stdout || '').trim().split(/\s+/)
  const width = Number(parts[0])
  const height = Number(parts[1])
  const nonWhitePct = Number(parts[2])
  if (!Number.isFinite(width) || !Number.isFinite(height) || !Number.isFinite(nonWhitePct)) {
    fail(`Pillow scan returned unparseable output: ${JSON.stringify(py.stdout)}`)
  }
  return { width, height, nonWhitePct, via: 'pillow' }
}

/**
 * @param {string} pngPath
 * @returns {Promise<{ width: number, height: number, nonWhitePct: number, via: string }>}
 */
async function scanPixels(pngPath) {
  const buf = fs.readFileSync(pngPath)
  if (buf.length < 8 || buf[0] !== 0x89 || buf.toString('ascii', 1, 4) !== 'PNG') {
    fail('AppIcon is not a PNG')
  }

  const require = createRequire(import.meta.url)

  const viaSharp = await trySharp(pngPath, buf, require)
  if (viaSharp) return viaSharp

  const viaCanvas = await tryNapiCanvas(pngPath, require)
  if (viaCanvas) return viaCanvas

  const viaPillow = tryPillow(pngPath)
  if (viaPillow) return viaPillow

  fail(
    'pixel scanner unavailable (need @napi-rs/canvas after npm ci, or sharp, or Pillow). Size-only checks are not accepted.',
  )
}

if (!fs.existsSync(iconPath)) fail(`missing ${iconPath}`)
if (!skipProject) assertProjectWiring()

const scan = await scanPixels(iconPath)
if (scan.width !== 1024 || scan.height !== 1024) {
  fail(`AppIcon must be 1024x1024, got ${scan.width}x${scan.height}`)
}
if (scan.nonWhitePct < 5) {
  fail(`AppIcon appears blank/white (non-white ${scan.nonWhitePct.toFixed(2)}%)`)
}

console.log(
  `assert-ios-appicon: ok size=${scan.width}x${scan.height} nonWhite=${scan.nonWhitePct.toFixed(1)}% via=${scan.via} path=${iconPath}`,
)
