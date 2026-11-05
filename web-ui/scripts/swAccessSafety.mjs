/**
 * Pure checks for FashionRise service-worker Access safety.
 * Shared by the CLI assert script and Vitest.
 */

/**
 * @param {string} source
 * @returns {{
 *   ok: boolean,
 *   errors: string[],
 *   hasNavigationRoute: boolean,
 *   hasCreateHandlerBoundToURL: boolean,
 *   hasNavigateFallbackLiteral: boolean,
 *   htmlPrecacheUrls: string[],
 * }}
 */
export function assertServiceWorkerAccessSafe(source) {
  const errors = []
  if (!source || typeof source !== 'string') {
    return {
      ok: false,
      errors: ['service worker source is empty'],
      hasNavigationRoute: false,
      hasCreateHandlerBoundToURL: false,
      hasNavigateFallbackLiteral: false,
      htmlPrecacheUrls: [],
    }
  }

  // Workbox generateSW emits NavigationRoute when navigateFallback is set.
  const hasNavigationRoute = /NavigationRoute/.test(source)
  // Bound-to-URL handler is how navigateFallback serves a cached HTML shell.
  const hasCreateHandlerBoundToURL = /createHandlerBoundToURL/.test(source)
  // Defensive: string form of a document fallback.
  const hasNavigateFallbackLiteral =
    /navigateFallback["']?\s*[:=]\s*["']\/?index\.html["']/.test(source) ||
    /["']\/index\.html["']\s*,\s*\{[^}]*navigate/.test(source)

  if (hasNavigationRoute) {
    errors.push('generated SW contains NavigationRoute (document navigations would bypass Access)')
  }
  if (hasCreateHandlerBoundToURL) {
    errors.push('generated SW contains createHandlerBoundToURL (HTML navigation fallback)')
  }
  if (hasNavigateFallbackLiteral) {
    errors.push('generated SW references navigateFallback index.html')
  }

  const htmlPrecacheUrls = extractHtmlPrecacheUrls(source)
  if (htmlPrecacheUrls.length > 0) {
    errors.push(`generated SW precaches HTML: ${htmlPrecacheUrls.join(', ')}`)
  }

  return {
    ok: errors.length === 0,
    errors,
    hasNavigationRoute,
    hasCreateHandlerBoundToURL,
    hasNavigateFallbackLiteral,
    htmlPrecacheUrls,
  }
}

/**
 * Extract .html URLs from the Workbox precache manifest embedded in sw.js.
 * @param {string} source
 * @returns {string[]}
 */
export function extractHtmlPrecacheUrls(source) {
  const urls = new Set()

  // Typical generateSW: precacheAndRoute([{url:"index.html",revision:"..."}, ...])
  const entryRe = /\{\s*url\s*:\s*["']([^"']+\.html)["']/g
  for (const match of source.matchAll(entryRe)) {
    urls.add(match[1])
  }

  // Also catch bare quoted html paths near precacheAndRoute payload.
  const precacheBlock = source.match(/precacheAndRoute\s*\(\s*(\[[\s\S]*?\])\s*(?:,|\))/ )
  if (precacheBlock) {
    const htmlInBlock = precacheBlock[1].matchAll(/["']([^"']+\.html)["']/g)
    for (const m of htmlInBlock) urls.add(m[1])
  }

  return [...urls].sort()
}

/**
 * @param {ReturnType<typeof assertServiceWorkerAccessSafe>} result
 * @param {string} [swPath]
 */
export function formatSwSafetyReport(result, swPath = 'sw.js') {
  const lines = [
    `sw_access_safety path=${swPath}`,
    `ok=${result.ok}`,
    `navigation_route=${result.hasNavigationRoute}`,
    `create_handler_bound_to_url=${result.hasCreateHandlerBoundToURL}`,
    `html_precache_count=${result.htmlPrecacheUrls.length}`,
  ]
  if (result.htmlPrecacheUrls.length) {
    lines.push(`html_precache=${result.htmlPrecacheUrls.join('|')}`)
  }
  for (const err of result.errors) {
    lines.push(`error=${err}`)
  }
  return lines.join('\n')
}
