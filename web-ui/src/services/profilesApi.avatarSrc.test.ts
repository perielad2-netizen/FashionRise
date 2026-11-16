import { describe, expect, it } from 'vitest'
import { profileAvatarSrc } from './profilesApi'

describe('profileAvatarSrc legacy + private compatibility', () => {
  const userId = '11111111-1111-1111-1111-111111111111'

  it('preserves legacy /static/uploads avatar URLs', () => {
    expect(profileAvatarSrc(userId, '/static/uploads/avatars/noa.jpg')).toBe(
      '/static/uploads/avatars/noa.jpg',
    )
    expect(
      profileAvatarSrc(userId, 'https://fashionrise.app/static/uploads/avatars/noa.jpg', 'v2'),
    ).toBe('https://fashionrise.app/static/uploads/avatars/noa.jpg?v=v2')
  })

  it('maps new private avatar API paths onto the owner avatar route', () => {
    expect(profileAvatarSrc(userId, `/api/v1/profiles/${userId}/avatar`)).toBe(
      `/api/v1/profiles/${userId}/avatar`,
    )
    expect(profileAvatarSrc(userId, `/api/v1/profiles/${userId}/avatar`, 'u9')).toBe(
      `/api/v1/profiles/${userId}/avatar?v=u9`,
    )
  })

  it('returns null when no avatar is set', () => {
    expect(profileAvatarSrc(userId, null)).toBeNull()
    expect(profileAvatarSrc(userId, undefined)).toBeNull()
    expect(profileAvatarSrc(userId, '')).toBeNull()
  })
})
