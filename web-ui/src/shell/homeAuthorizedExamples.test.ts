import { describe, expect, it } from 'vitest'
import {
  AUTHORIZED_HOME_EXAMPLES,
  getAuthorizedHomeExamples,
  isAuthorizedHomeExample,
  type AuthorizedHomeExample,
} from './homeAuthorizedExamples'

const validPair: AuthorizedHomeExample = {
  id: 'fixture-1',
  title: 'Fixture gown',
  authorization: {
    source: 'PM fixture for unit tests only',
    licensedFor: 'home-marketing',
  },
  before: {
    src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"/>',
    alt: 'Sketch of a gown',
    width: 60,
    height: 80,
  },
  after: {
    src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"/>',
    alt: 'Magic look of a gown',
    width: 60,
    height: 80,
  },
}

describe('homeAuthorizedExamples', () => {
  it('ships an empty production catalog until PM authorizes real pairs', () => {
    expect(AUTHORIZED_HOME_EXAMPLES).toEqual([])
    expect(getAuthorizedHomeExamples()).toEqual([])
  })

  it('accepts only rows with home-marketing authorization and sized images', () => {
    expect(isAuthorizedHomeExample(validPair)).toBe(true)
    expect(
      isAuthorizedHomeExample({
        ...validPair,
        authorization: { source: 'x', licensedFor: 'runway' },
      } as unknown),
    ).toBe(false)
    expect(
      isAuthorizedHomeExample({
        ...validPair,
        before: { ...validPair.before, width: 0 },
      }),
    ).toBe(false)
  })

  it('filters invalid rows from a catalog override', () => {
    const mixed = [
      validPair,
      { id: 'bad', title: 'no auth' },
    ] as readonly AuthorizedHomeExample[]
    expect(getAuthorizedHomeExamples(mixed)).toEqual([validPair])
  })
})
