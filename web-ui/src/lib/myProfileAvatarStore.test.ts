import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  __myProfileAvatarStoreTestUtils,
  peekMyProfileAvatar,
  publishMyProfileAvatar,
  subscribeMyProfileAvatar,
} from './myProfileAvatarStore'

describe('myProfileAvatarStore', () => {
  afterEach(() => {
    __myProfileAvatarStoreTestUtils.clear()
  })

  it('publishes avatar updates to subscribers', () => {
    const listener = vi.fn()
    const unsub = subscribeMyProfileAvatar(listener)
    publishMyProfileAvatar('u1', '/api/v1/profiles/u1/avatar')
    expect(peekMyProfileAvatar()).toEqual({
      userId: 'u1',
      avatarUrl: '/api/v1/profiles/u1/avatar',
    })
    expect(listener).toHaveBeenCalledWith('/api/v1/profiles/u1/avatar')
    unsub()
    publishMyProfileAvatar('u1', null)
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
