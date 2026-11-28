/**
 * Service-worker sanitizer tests — load push-sw-handlers.js in a fake self.
 * Run: node --test public/push-sw-handlers.test.mjs (from web-ui)
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import cases from './__fixtures__/push_destination_contract_cases.json' with { type: 'json' }

const __dirname = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(__dirname, 'push-sw-handlers.js'), 'utf8')

const listeners = {}
const fakeSelf = {
  addEventListener(type, fn) {
    listeners[type] = fn
  },
  __frSanitizePushUrl: null,
}
;(function runInSwScope() {
  // eslint-disable-next-line no-new-func
  const fn = new Function('self', source)
  fn(fakeSelf)
})()

const sanitize = fakeSelf.__frSanitizePushUrl
assert.equal(typeof sanitize, 'function')

test('SW shared contract fixtures', () => {
  for (const row of cases) {
    assert.equal(sanitize(row.input), row.expected, row.id)
  }
})

test('SW push event stores sanitized url on notification data', async () => {
  const shown = []
  const registration = {
    showNotification(title, opts) {
      shown.push({ title, opts })
      return Promise.resolve()
    },
  }
  Object.defineProperty(fakeSelf, 'registration', { value: registration, configurable: true })
  const item =
    '/studio/fashionrise?item=11111111-1111-4111-8111-111111111111&comments=1&comment=22222222-2222-4222-8222-222222222222'
  const event = {
    data: {
      json: () => ({ title: 'T', body: 'B', url: item, tag: 't' }),
    },
    waitUntil(p) {
      return p
    },
  }
  listeners.push(event)
  await Promise.resolve()
  assert.equal(shown.length, 1)
  assert.equal(shown[0].opts.data.url, item)
})

test('SW notificationclick re-sanitizes destination', async () => {
  const navigated = []
  const clients = {
    matchAll: async () => [
      {
        focus: async () => {},
        navigate: async (url) => {
          navigated.push(url)
        },
      },
    ],
  }
  Object.defineProperty(fakeSelf, 'clients', { value: clients, configurable: true })
  let pending = null
  const event = {
    notification: {
      close() {},
      data: { url: 'javascript:alert(1)' },
    },
    waitUntil(p) {
      pending = Promise.resolve(p)
    },
  }
  listeners.notificationclick(event)
  await pending
  assert.deepEqual(navigated, ['/studio/fashionrise'])
})
