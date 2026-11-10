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

  it('keeps the committed iOS capacitor.config.json in sync (Codemagic source)', () => {
    const native = readFileSync(
      path.resolve(__dirname, '../../../ios/App/App/capacitor.config.json'),
      'utf8',
    )
    const parsed = JSON.parse(native) as { ios?: { contentInset?: string } }
    expect(parsed.ios?.contentInset).toBe('never')
    expect(native).not.toMatch(/"contentInset"\s*:\s*"automatic"/)
  })

  it('overlays the status bar so the WebView is edge-to-edge', () => {
    const boot = readFileSync(path.resolve(__dirname, './bootstrap.ts'), 'utf8')
    expect(boot).toMatch(/setOverlaysWebView\(\{\s*overlay:\s*true\s*\}\)/)
    expect(boot).toContain("classList.add('fr-native-shell')")
  })
})
