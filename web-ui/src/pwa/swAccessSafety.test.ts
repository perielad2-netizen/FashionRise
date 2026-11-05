import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  assertServiceWorkerAccessSafe,
  extractHtmlPrecacheUrls,
} from '../../scripts/swAccessSafety.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const distSw = path.join(rootDir, 'dist', 'sw.js')

describe('swAccessSafety helpers', () => {
  it('rejects a Workbox SW that precaches index.html and installs NavigationRoute', () => {
    const bad = `
      import {precaching, routing, strategies} from 'workbox';
      precaching.precacheAndRoute([
        {url:"index.html",revision:"abc"},
        {url:"assets/app.js",revision:"def"}
      ]);
      routing.registerRoute(new routing.NavigationRoute(
        strategies.createHandlerBoundToURL("index.html")
      ));
    `
    const result = assertServiceWorkerAccessSafe(bad)
    expect(result.ok).toBe(false)
    expect(result.hasNavigationRoute).toBe(true)
    expect(result.hasCreateHandlerBoundToURL).toBe(true)
    expect(result.htmlPrecacheUrls).toContain('index.html')
  })

  it('accepts an asset-only precache without navigation fallback', () => {
    const good = `
      precacheAndRoute([
        {url:"assets/index-abc.js",revision:null},
        {url:"assets/index-def.css",revision:null},
        {url:"icons/icon-192.png",revision:"1"}
      ]);
      cleanupOutdatedCaches();
    `
    const result = assertServiceWorkerAccessSafe(good)
    expect(result.ok).toBe(true)
    expect(result.htmlPrecacheUrls).toEqual([])
    expect(extractHtmlPrecacheUrls(good)).toEqual([])
  })

  it('fails closed on empty source', () => {
    expect(assertServiceWorkerAccessSafe('').ok).toBe(false)
  })
})

describe('unsafe SW fixture (red path)', () => {
  it('fails closed on the checked-in unsafe fixture', () => {
    const fixture = path.join(
      rootDir,
      'scripts/fixtures/unsafe-sw-with-html-navigation.js',
    )
    expect(existsSync(fixture)).toBe(true)
    const source = readFileSync(fixture, 'utf8')
    const result = assertServiceWorkerAccessSafe(source)
    expect(result.ok).toBe(false)
    expect(result.htmlPrecacheUrls).toContain('index.html')
    expect(result.hasNavigationRoute).toBe(true)
    expect(result.hasCreateHandlerBoundToURL).toBe(true)
  })
})

describe('generated production dist/sw.js (post-build artifact)', () => {
  it('has no HTML precache and no NavigationRoute when dist exists', () => {
    if (!existsSync(distSw)) {
      // Local `npm test` without a prior build still exercises the helpers above.
      // Standard `npm run build` embeds the Access safety assert after Vite.
      expect(existsSync(distSw)).toBe(false)
      return
    }
    const source = readFileSync(distSw, 'utf8')
    const result = assertServiceWorkerAccessSafe(source)
    expect(result.errors).toEqual([])
    expect(result.ok).toBe(true)
    expect(source).not.toMatch(/NavigationRoute/)
    expect(source).not.toMatch(/createHandlerBoundToURL/)
    expect(extractHtmlPrecacheUrls(source)).toEqual([])
  })
})
