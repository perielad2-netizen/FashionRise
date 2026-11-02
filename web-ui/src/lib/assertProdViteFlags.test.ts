/**
 * P0 #136 — each production VITE gate mismatch must fail independently.
 * Imports pure helpers from scripts/assert-prod-vite-flags.mjs.
 */
import { describe, expect, it } from 'vitest'
import {
  assertCompiledApiBase,
  assertCompiledGatesMatchAllowlist,
  assertCompiledNoticesPresent,
  assertCroquisNoticeEnv,
  assertNodeEnvAllowlist,
  extractCompiledGates,
  EXPECTED_PROD_NOTICE_SHA256,
  EXPECTED_PROD_VITE_FLAGS,
  sha256Hex,
} from '../../scripts/assert-prod-vite-flags.mjs'

function synthBundle({
  frontBack = true,
  dual = true,
  magic = true,
  registration = false,
}: {
  frontBack?: boolean
  dual?: boolean
  magic?: boolean
  registration?: boolean
}) {
  const fb = frontBack ? '!0' : '!1'
  const du = dual ? '!0' : '!1'
  const mg = magic ? '!0' : '!1'
  const rg = registration ? '!0' : '!1'
  return [
    `function Es(){return${fb}}`,
    `function jx(){return${du}}`,
    `function dS(){return${mg}}`,
    `function Ii(){return${rg}}`,
    `let n=t?.frontBackEnabled??Es();`,
    `a=Es(),o=jx(),s=1`,
    `,Ze=dS(),Qe=busy`,
    'path:`/register`,element:Ii()?(0,V.jsx)(Mo,{}):(0,V.jsx)(zt,{to:`/login`})',
  ].join('')
}

describe('assert-prod-vite-flags compiled extraction', () => {
  it('accepts a bundle with all gates matching the allowlist', () => {
    const gates = extractCompiledGates(synthBundle({}))
    expect(assertCompiledGatesMatchAllowlist(gates)).toEqual([])
    expect(gates.frontBack.value).toBe(true)
    expect(gates.dualMagic.value).toBe(true)
    expect(gates.magicUi.value).toBe(true)
    expect(gates.registration.value).toBe(false)
  })

  it('fails when only Front/Back is compiled off', () => {
    const gates = extractCompiledGates(synthBundle({ frontBack: false }))
    const failures = assertCompiledGatesMatchAllowlist(gates)
    expect(failures.some((f) => f.includes('VITE_STUDIO_FRONT_BACK_ENABLED'))).toBe(true)
    expect(failures.some((f) => f.includes('VITE_MAGIC_UI_ENABLED'))).toBe(false)
  })

  it('fails when only Magic UI is compiled off', () => {
    const gates = extractCompiledGates(synthBundle({ magic: false }))
    const failures = assertCompiledGatesMatchAllowlist(gates)
    expect(failures.some((f) => f.includes('VITE_MAGIC_UI_ENABLED'))).toBe(true)
    expect(failures.some((f) => f.includes('VITE_STUDIO_FRONT_BACK_ENABLED'))).toBe(false)
  })

  it('fails when only Dual Magic is compiled off', () => {
    const gates = extractCompiledGates(synthBundle({ dual: false }))
    const failures = assertCompiledGatesMatchAllowlist(gates)
    expect(failures.some((f) => f.includes('VITE_STUDIO_DUAL_MAGIC_ENABLED'))).toBe(true)
  })

  it('fails when Registration is compiled on', () => {
    const gates = extractCompiledGates(synthBundle({ registration: true }))
    const failures = assertCompiledGatesMatchAllowlist(gates)
    expect(failures.some((f) => f.includes('VITE_REGISTRATION_UI_ENABLED'))).toBe(true)
  })
})

describe('assert-prod-vite-flags Node env allowlist', () => {
  const good = {
    VITE_API_BASE_URL: '/api/v1',
    VITE_REGISTRATION_UI_ENABLED: 'false',
    VITE_MAGIC_UI_ENABLED: 'true',
    VITE_STUDIO_FRONT_BACK_ENABLED: 'true',
    VITE_STUDIO_DUAL_MAGIC_ENABLED: 'true',
  }

  it('accepts explicit good exports', () => {
    expect(assertNodeEnvAllowlist(good)).toEqual([])
  })

  it('treats unset registration as false', () => {
    const { VITE_REGISTRATION_UI_ENABLED: _r, ...rest } = good
    expect(assertNodeEnvAllowlist(rest)).toEqual([])
  })

  it('fails when Magic env is missing (Vite .env.production alone is not enough)', () => {
    const { VITE_MAGIC_UI_ENABLED: _m, ...rest } = good
    const failures = assertNodeEnvAllowlist(rest)
    expect(failures.some((f) => f.includes('VITE_MAGIC_UI_ENABLED'))).toBe(true)
    expect(failures.some((f) => f.includes('Export VITE_* explicitly'))).toBe(true)
  })

  it('fails independently when only Front/Back env is false', () => {
    const failures = assertNodeEnvAllowlist({
      ...good,
      VITE_STUDIO_FRONT_BACK_ENABLED: 'false',
    })
    expect(failures).toHaveLength(1)
    expect(failures[0]).toContain('VITE_STUDIO_FRONT_BACK_ENABLED')
  })

  it('records allowlist constants used by production builds', () => {
    expect(EXPECTED_PROD_VITE_FLAGS.VITE_MAGIC_UI_ENABLED).toBe(true)
    expect(EXPECTED_PROD_VITE_FLAGS.VITE_STUDIO_FRONT_BACK_ENABLED).toBe(true)
    expect(EXPECTED_PROD_VITE_FLAGS.VITE_STUDIO_DUAL_MAGIC_ENABLED).toBe(true)
    expect(EXPECTED_PROD_VITE_FLAGS.VITE_REGISTRATION_UI_ENABLED).toBe(false)
  })
})

describe('assert-prod-vite-flags compiled API base', () => {
  it('accepts relative /api/v1', () => {
    expect(assertCompiledApiBase('const x=`/api/v1`;')).toEqual([])
  })

  it('fails when /api/v1 is missing', () => {
    expect(assertCompiledApiBase('const x="/api/v2"').some((f) => f.includes('missing'))).toBe(true)
  })

  it('fails when localhost API base is embedded', () => {
    const failures = assertCompiledApiBase('fetch("http://localhost:8001/api/v1") `/api/v1`')
    expect(failures.some((f) => f.includes('localhost'))).toBe(true)
  })
})

describe('assert-prod-vite-flags croquis notices (#158)', () => {
  const adults = 'Approved adults notice body for production assert coverage.'
  const storage = 'Approved storage notice body for production assert coverage.'
  const ai = 'Approved AI notice body for production assert coverage.'
  const goodNotices = {
    VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT: adults,
    VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT: storage,
    VITE_MY_CROQUIS_AI_NOTICE_TEXT: ai,
    EXPECTED_MY_CROQUIS_ADULTS_NOTICE_TEXT_SHA256: sha256Hex(adults),
    EXPECTED_MY_CROQUIS_STORAGE_NOTICE_TEXT_SHA256: sha256Hex(storage),
    EXPECTED_MY_CROQUIS_AI_NOTICE_TEXT_SHA256: sha256Hex(ai),
  }

  it('accepts approved notices matching expected SHA256 overrides', () => {
    const { failures, notices } = assertCroquisNoticeEnv(goodNotices)
    expect(failures).toEqual([])
    expect(notices.VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT.sha256).toBe(sha256Hex(adults))
  })

  it('fails when any notice is empty (dynamic import.meta.env regression)', () => {
    const { failures } = assertCroquisNoticeEnv({
      ...goodNotices,
      VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT: '',
    })
    expect(failures.some((f) => f.includes('VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT'))).toBe(true)
  })

  it('fails when notice text is a draft/placeholder', () => {
    const { failures } = assertCroquisNoticeEnv({
      ...goodNotices,
      VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT: 'DRAFT placeholder — not legal',
    })
    expect(failures.some((f) => f.includes('VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT'))).toBe(true)
  })

  it('fails when SHA256 does not match expected production digest', () => {
    const { failures } = assertCroquisNoticeEnv({
      VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT: adults,
      VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT: storage,
      VITE_MY_CROQUIS_AI_NOTICE_TEXT: ai,
      // force default expected digests (prod) which will not match synthetic text
    })
    expect(failures.length).toBeGreaterThan(0)
    expect(failures[0]).toContain('SHA256')
    expect(EXPECTED_PROD_NOTICE_SHA256.VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT).toMatch(/^[a-f0-9]{64}$/)
  })

  it('proves notices are embedded in the compiled bundle', () => {
    const { notices } = assertCroquisNoticeEnv(goodNotices)
    const bundle = `prelude${adults}mid${storage}end${ai}`
    expect(assertCompiledNoticesPresent(bundle, notices)).toEqual([])
    expect(
      assertCompiledNoticesPresent(`prelude${adults}mid${storage}`, notices).some((f) =>
        f.includes('VITE_MY_CROQUIS_AI_NOTICE_TEXT'),
      ),
    ).toBe(true)
  })
})
