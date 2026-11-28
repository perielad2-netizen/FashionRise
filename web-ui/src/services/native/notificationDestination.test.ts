import { describe, expect, it } from 'vitest'
import { extractNotificationDestinationUrl } from './notificationDestination'

const ITEM = '11111111-1111-4111-8111-111111111111'
const COMMENT = '22222222-2222-4222-8222-222222222222'
const FRIENDSHIP = '33333333-3333-4333-8333-333333333333'

const COMMENT_URL = `/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`
const LIKE_URL = `/studio/fashionrise?item=${ITEM}`
const FRIEND_REQ = `/studio/fashionrise?friends=1&section=requests&friendship=${FRIENDSHIP}`
const FRIEND_OK = `/studio/fashionrise?friends=1&section=accepted&friendship=${FRIENDSHIP}`

describe('extractNotificationDestinationUrl', () => {
  it('reads Android-style flat FCM extras (data.url)', () => {
    expect(
      extractNotificationDestinationUrl({
        data: { url: COMMENT_URL, tag: `fr-comment-${COMMENT}` },
      }),
    ).toBe(COMMENT_URL)
  })

  it('reads iOS Cap userInfo with aps + root url (build 205 shape)', () => {
    // PushNotificationsHandler.swift: notification.data = full APNs userInfo
    expect(
      extractNotificationDestinationUrl({
        data: {
          aps: { alert: { title: 'New comment', body: 'hi' }, sound: 'default' },
          url: COMMENT_URL,
          tag: `fr-comment-${COMMENT}`,
        },
      }),
    ).toBe(COMMENT_URL)
  })

  it('reads nested data.url bag (hardened APNs body)', () => {
    expect(
      extractNotificationDestinationUrl({
        data: {
          aps: { alert: { title: 'x', body: 'y' } },
          data: { url: LIKE_URL, tag: `fr-like-${ITEM}` },
        },
      }),
    ).toBe(LIKE_URL)
  })

  it('covers six social event destination shapes', () => {
    const cases = [
      LIKE_URL,
      `/studio/fashionrise?item=${ITEM}`, // score shares item URL
      COMMENT_URL,
      COMMENT_URL, // comment like
      FRIEND_REQ,
      FRIEND_OK,
    ]
    for (const url of cases) {
      expect(extractNotificationDestinationUrl({ data: { url } })).toBe(url)
      expect(
        extractNotificationDestinationUrl({
          data: { aps: {}, url, data: { url } },
        }),
      ).toBe(url)
    }
  })

  it('returns null when no destination is present', () => {
    expect(extractNotificationDestinationUrl({ data: { aps: { alert: 'x' } } })).toBeNull()
    expect(extractNotificationDestinationUrl(null)).toBeNull()
    expect(extractNotificationDestinationUrl({ data: {} })).toBeNull()
  })

  it('prefers notification.link when data lacks url', () => {
    expect(
      extractNotificationDestinationUrl({
        data: { aps: {} },
        link: COMMENT_URL,
      }),
    ).toBe(COMMENT_URL)
  })
})
