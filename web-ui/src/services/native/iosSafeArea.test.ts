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

  it('overlays the status bar so the WebView is edge-to-edge', () => {
    const boot = readFileSync(path.resolve(__dirname, './bootstrap.ts'), 'utf8')
    expect(boot).toMatch(/setOverlaysWebView\(\{\s*overlay:\s*true\s*\}\)/)
    expect(boot).toContain("classList.add('fr-native-shell')")
  })
})
