import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * iOS kills the app when WKWebView file inputs open the camera without
 * NSCameraUsageDescription. Pin the privacy strings shipped in Info.plist.
 */
describe('iOS privacy usage strings (Create Model camera)', () => {
  const plist = readFileSync(
    path.resolve(__dirname, '../../../ios/App/App/Info.plist'),
    'utf8',
  )

  it('declares camera usage for Take Photo from Create Model file input', () => {
    expect(plist).toContain('<key>NSCameraUsageDescription</key>')
    expect(plist).toMatch(/Create Model/i)
    expect(plist).toMatch(/camera/i)
  })

  it('declares photo library usage for Photo Library / Choose File', () => {
    expect(plist).toContain('<key>NSPhotoLibraryUsageDescription</key>')
    expect(plist).toContain('<key>NSPhotoLibraryAddUsageDescription</key>')
  })
})
