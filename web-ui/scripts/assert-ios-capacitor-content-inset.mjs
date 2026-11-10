#!/usr/bin/env node
/**
 * Fail closed if the iOS Capacitor config would double-pad under the status bar.
 * Run after `npx cap sync ios` (Codemagic) so TestFlight never ships contentInset automatic.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const nativeCfg = path.join(root, 'ios/App/App/capacitor.config.json')
const tsCfg = path.join(root, 'capacitor.config.ts')

const ts = fs.readFileSync(tsCfg, 'utf8')
if (!/contentInset:\s*'never'/.test(ts) || /contentInset:\s*'automatic'/.test(ts)) {
  console.error('assert-ios-capacitor-content-inset: capacitor.config.ts must set contentInset: never')
  process.exit(1)
}

if (!fs.existsSync(nativeCfg)) {
  console.error('assert-ios-capacitor-content-inset: missing', nativeCfg, '(run npx cap sync ios first)')
  process.exit(1)
}

const parsed = JSON.parse(fs.readFileSync(nativeCfg, 'utf8'))
const inset = parsed?.ios?.contentInset
if (inset !== 'never') {
  // Belt-and-suspenders: rewrite before failing closed on a second pass.
  parsed.ios = { ...(parsed.ios || {}), contentInset: 'never' }
  fs.writeFileSync(nativeCfg, `${JSON.stringify(parsed, null, '\t')}\n`)
  console.warn('assert-ios-capacitor-content-inset: rewrote contentInset automatic → never')
}

const again = JSON.parse(fs.readFileSync(nativeCfg, 'utf8'))
if (again?.ios?.contentInset !== 'never') {
  console.error('assert-ios-capacitor-content-inset: native config still not never after rewrite')
  process.exit(1)
}

console.log('assert-ios-capacitor-content-inset: ok (contentInset=never)')
