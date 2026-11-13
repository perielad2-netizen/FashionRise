/**
 * Static verification that iOS native push wiring stays intact without an Xcode build.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const iosApp = resolve(__dirname, '../../../ios/App')

describe('iOS APNs / Capacitor push wiring', () => {
  it('AppDelegate forwards APNs success and failure to Capacitor', () => {
    const src = readFileSync(resolve(iosApp, 'App/AppDelegate.swift'), 'utf8')
    expect(src).toContain('didRegisterForRemoteNotificationsWithDeviceToken')
    expect(src).toContain('didFailToRegisterForRemoteNotificationsWithError')
    expect(src).toContain('.capacitorDidRegisterForRemoteNotifications')
    expect(src).toContain('.capacitorDidFailToRegisterForRemoteNotifications')
    expect(src).toContain('NotificationCenter.default.post')
  })

  it('Debug entitlements use development APNs; Release uses production', () => {
    const debug = readFileSync(resolve(iosApp, 'App/AppDebug.entitlements'), 'utf8')
    const release = readFileSync(resolve(iosApp, 'App/AppRelease.entitlements'), 'utf8')
    expect(debug).toMatch(/<key>aps-environment<\/key>\s*<string>development<\/string>/)
    expect(release).toMatch(/<key>aps-environment<\/key>\s*<string>production<\/string>/)
    for (const xml of [debug, release]) {
      expect(xml).toContain('applinks:fashionrise.app')
      expect(xml).toContain('com.apple.developer.associated-domains')
    }
  })

  it('Xcode project points Debug/Release at the matching entitlements files', () => {
    const pbx = readFileSync(resolve(iosApp, 'App.xcodeproj/project.pbxproj'), 'utf8')
    expect(pbx).toContain('CODE_SIGN_ENTITLEMENTS = App/AppDebug.entitlements')
    expect(pbx).toContain('CODE_SIGN_ENTITLEMENTS = App/AppRelease.entitlements')
    expect(pbx).not.toContain('CODE_SIGN_ENTITLEMENTS = App/App.entitlements')
  })

  it('Info.plist declares remote-notification background mode', () => {
    const plist = readFileSync(resolve(iosApp, 'App/Info.plist'), 'utf8')
    expect(plist).toContain('UIBackgroundModes')
    expect(plist).toContain('remote-notification')
  })
})
