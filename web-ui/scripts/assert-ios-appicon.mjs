#!/usr/bin/env node
/**
 * Fail closed if the Capacitor iOS AppIcon asset is missing, wrong size/mode,
 * or blank (all-white). A white 1024 PNG looks like a "placeholder" on Apple's
 * purchase sheet even though Xcode builds succeed.
 *
 * Pixel validation requires sharp OR Python Pillow. There is no size-only
 * success path — missing scanners fail the build.
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
  let sharp
  try {
    sharp = require('sharp')
  } catch {
    sharp = null
  }

  if (sharp) {
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

  // Fail closed: Pillow must succeed when sharp is absent.
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
    # Flatten only after rejecting true alpha usage for App Store icon.
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

  if (py.error) {
    fail(`pixel scanner unavailable (no sharp, python3 error: ${py.error.message})`)
  }
  if (py.status === 3) fail('AppIcon must not have alpha (App Store rejects transparency)')
  if (py.status === 4) fail(`AppIcon must be 1024x1024 (${(py.stderr || '').trim()})`)
  if (py.status !== 0) {
    fail(
      `Pillow pixel scan failed (exit ${py.status}). Install Pillow or sharp — size-only checks are not accepted. ${(py.stderr || py.stdout || '').trim()}`,
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
