import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

describe('iOS Capacitor safe-area wiring', () => {
  it('uses contentInset never so CSS safe-area is not double-applied', () => {
    const cfg = readFileSync(
      path.resolve(__dirname, '../../../capacitor.config.ts'),
      'utf8',
    )
    expect(cfg).toMatch(/contentInset:\s*'never'/)
    expect(cfg).not.toMatch(/contentInset:\s*'automatic'/)
  })

  it('ships a Codemagic assert that rewrites native contentInset to never', () => {
    const script = readFileSync(
      path.resolve(__dirname, '../../../scripts/assert-ios-capacitor-content-inset.mjs'),
      'utf8',
    )
    expect(script).toContain("contentInset: 'never'")
    expect(script).toContain('rewrote contentInset')
    const yaml = readFileSync(path.resolve(__dirname, '../../../../codemagic.yaml'), 'utf8')
    expect(yaml).toContain('assert-ios-capacitor-content-inset.mjs')
  })

  it('overlays the status bar so the WebView is edge-to-edge', () => {
    const boot = readFileSync(path.resolve(__dirname, './bootstrap.ts'), 'utf8')
    expect(boot).toMatch(/setOverlaysWebView\(\{\s*overlay:\s*true\s*\}\)/)
    expect(boot).toContain("classList.add('fr-native-shell')")
  })
})
