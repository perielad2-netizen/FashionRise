#!/usr/bin/env node
/**
 * Fail closed if the Capacitor iOS AppIcon asset is missing, wrong size/mode,
 * or blank (all-white). A white 1024 PNG looks like a "placeholder" on Apple's
 * purchase sheet even though Xcode builds succeed.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const iconPath = path.join(
  root,
  'ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png',
)
const contentsPath = path.join(
  root,
  'ios/App/App/Assets.xcassets/AppIcon.appiconset/Contents.json',
)
const pbxproj = path.join(root, 'ios/App/App.xcodeproj/project.pbxproj')

function fail(msg) {
  console.error(`assert-ios-appicon: FAIL — ${msg}`)
  process.exit(1)
}

if (!fs.existsSync(iconPath)) fail(`missing ${iconPath}`)
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

const require = createRequire(import.meta.url)
let sharp
try {
  sharp = require('sharp')
} catch {
  // sharp is optional in some CI images — fall back to PNG header + sampling via zlib
  sharp = null
}

const buf = fs.readFileSync(iconPath)
if (buf.length < 10_000) fail(`AppIcon too small (${buf.length} bytes) — likely blank/stub`)

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
  const pct = (100 * nonWhite) / (info.width * info.height)
  if (pct < 5) fail(`AppIcon appears blank/white (non-white ${pct.toFixed(2)}%)`)
  console.log(
    `assert-ios-appicon: ok size=${info.width}x${info.height} channels=${channels} nonWhite=${pct.toFixed(1)}% bytes=${buf.length}`,
  )
} else {
  // Minimal PNG IHDR check without sharp, then Pillow blank-white scan when available.
  if (buf[0] !== 0x89 || buf.toString('ascii', 1, 4) !== 'PNG') fail('AppIcon is not a PNG')
  const w = buf.readUInt32BE(16)
  const h = buf.readUInt32BE(20)
  if (w !== 1024 || h !== 1024) fail(`AppIcon must be 1024x1024, got ${w}x${h}`)
  // Prefer Python/Pillow on Codemagic / agents (sharp often absent).
  try {
    const { spawnSync } = await import('node:child_process')
    const py = spawnSync(
      'python3',
      [
        '-c',
        `from PIL import Image; im=Image.open(${JSON.stringify(iconPath)}).convert("RGB");
w,h=im.size; assert (w,h)==(1024,1024);
nw=sum(1 for p in im.getdata() if p!=(255,255,255));
pct=100*nw/(w*h); print(f"nonwhite={pct:.2f}");
raise SystemExit(0 if pct>=5 else 2)`,
      ],
      { encoding: 'utf8' },
    )
    if (py.status === 2) fail('AppIcon appears blank/white (Pillow scan)')
    if (py.status !== 0) {
      console.warn('assert-ios-appicon: Pillow scan skipped:', (py.stderr || py.stdout || '').trim())
    } else {
      console.log(`assert-ios-appicon: ok size=${w}x${h} bytes=${buf.length} ${py.stdout.trim()}`)
      process.exit(0)
    }
  } catch (err) {
    console.warn('assert-ios-appicon: Pillow scan unavailable', err)
  }
  // Size heuristic: the historical blank white stub was ~110 KB; real emblem icon is larger.
  if (buf.length < 150_000) {
    fail(
      `AppIcon bytes=${buf.length} look like the blank-white stub; regenerate from branding emblem`,
    )
  }
  console.log(`assert-ios-appicon: ok (header+size) size=${w}x${h} bytes=${buf.length}`)
}
