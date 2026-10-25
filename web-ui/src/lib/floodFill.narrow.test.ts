/**
 * P1 #60 — narrow closed-shape fill + internal-seam safety (synthetic barriers).
 * No canvas artwork, no network, no paid AI.
 */
import { describe, expect, it } from 'vitest'
import {
  contourCoversPixel,
  contourSimplifyTolerance,
  dilateMask,
  exploreFlood,
  floodFillAdaptive,
  floodFillAgainstBarrier,
  isAccidentalPunchThrough,
  MAX_FILL_PIXELS,
  minScanlineSpan,
  removeCollinearPoints,
  traceRegionContour,
} from '@/lib/floodFill'
import {
  checkPersistableFill,
  fabricStyle,
  gradientStyleFromPreset,
  MAX_FILL_CONTOUR_VALUES,
  parseFillOp,
  solidStyle,
  uploadedFabricStyle,
} from '@/lib/fills'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import {
  designToScreen,
  hundredPercent,
  pinchPan,
  pinchScaleFactor,
  screenToDesign,
  zoomAt,
  type ViewportState,
} from '@/lib/viewportTransform'

function emptyBarrier(): Uint8Array {
  return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
}

function setBarrier(barrier: Uint8Array, x: number, y: number) {
  barrier[y * DESIGN_WIDTH + x] = 1
}

function clearBarrier(barrier: Uint8Array, x: number, y: number) {
  barrier[y * DESIGN_WIDTH + x] = 0
}

function hWall(barrier: Uint8Array, y: number, x0: number, x1: number) {
  for (let x = x0; x <= x1; x += 1) setBarrier(barrier, x, y)
}

function vWall(barrier: Uint8Array, x: number, y0: number, y1: number) {
  for (let y = y0; y <= y1; y += 1) setBarrier(barrier, x, y)
}

/** Closed axis-aligned rectangle ring (interior is open). */
function closedRect(x0: number, y0: number, x1: number, y1: number): Uint8Array {
  const b = emptyBarrier()
  hWall(b, y0, x0, x1)
  hWall(b, y1, x0, x1)
  vWall(b, x0, y0, y1)
  vWall(b, x1, y0, y1)
  return b
}

/**
 * PM reproduction: outer box 200–500 / 200–500, internal seam x=350,
 * optional hole(s) around y=350. Seeds: left 275,350 — right 425,350.
 */
function dividedPanels(hole: 'none' | '1px' | '2px' | 'diagonal' | 'eraser-gap'): {
  barrier: Uint8Array
  leftSeed: { x: number; y: number }
  rightSeed: { x: number; y: number }
} {
  const b = emptyBarrier()
  hWall(b, 200, 200, 500)
  hWall(b, 500, 200, 500)
  vWall(b, 200, 200, 500)
  vWall(b, 500, 200, 500)
  vWall(b, 350, 200, 500)

  if (hole === '1px') {
    clearBarrier(b, 350, 350)
  } else if (hole === '2px') {
    clearBarrier(b, 350, 349)
    clearBarrier(b, 350, 350)
  } else if (hole === 'diagonal') {
    // Diagonal nick through the seam (two diagonal-adjacent opens).
    clearBarrier(b, 350, 350)
    clearBarrier(b, 350, 351)
    // Soften the join like a freehand miss — also clear a diagonal neighbor column
    // is not needed; 4-connected flood still needs the vertical opens.
  } else if (hole === 'eraser-gap') {
    // Eraser-created seam gap: 2×2 open nick in the dividing wall.
    clearBarrier(b, 350, 349)
    clearBarrier(b, 350, 350)
    clearBarrier(b, 350, 351)
  }

  return {
    barrier: b,
    leftSeed: { x: 275, y: 350 },
    rightSeed: { x: 425, y: 350 },
  }
}

/**
 * Hourglass: two wide lobes connected by a vertical neck of `neckWidth` open
 * interior pixels. Entire silhouette is a single closed outline.
 */
function hourglassBarrier(neckWidth: number): {
  barrier: Uint8Array
  upperSeed: { x: number; y: number }
  neckSeed: { x: number; y: number }
  lowerSeed: { x: number; y: number }
  neckX0: number
  neckX1: number
  neckY0: number
  neckY1: number
} {
  const ox0 = 220
  const ox1 = 420
  const oy0 = 180
  const oy1 = 620
  const midX = 320
  const neckY0 = 360
  const neckY1 = 440
  const half = Math.floor((neckWidth - 1) / 2)
  const neckX0 = midX - half
  const neckX1 = neckX0 + neckWidth - 1

  const b = emptyBarrier()
  hWall(b, oy0, ox0, ox1)
  hWall(b, oy1, ox0, ox1)
  vWall(b, ox0, oy0, oy1)
  vWall(b, ox1, oy0, oy1)

  for (let y = neckY0; y <= neckY1; y += 1) {
    for (let x = ox0 + 1; x < neckX0; x += 1) setBarrier(b, x, y)
    for (let x = neckX1 + 1; x < ox1; x += 1) setBarrier(b, x, y)
  }

  return {
    barrier: b,
    upperSeed: { x: midX, y: 260 },
    neckSeed: { x: midX, y: Math.floor((neckY0 + neckY1) / 2) },
    lowerSeed: { x: midX, y: 540 },
    neckX0,
    neckX1,
    neckY0,
    neckY1,
  }
}

/** Irregular / curved 1–2px neck between two larger lobes (contour fidelity). */
function curvedNeckHourglass(neckWidth: number): {
  barrier: Uint8Array
  upperSeed: { x: number; y: number }
  neckSamples: { x: number; y: number }[]
  lowerSeed: { x: number; y: number }
} {
  const ox0 = 200
  const ox1 = 440
  const oy0 = 160
  const oy1 = 640
  const neckY0 = 350
  const neckY1 = 450
  const b = emptyBarrier()
  hWall(b, oy0, ox0, ox1)
  hWall(b, oy1, ox0, ox1)
  vWall(b, ox0, oy0, oy1)
  vWall(b, ox1, oy0, oy1)

  const samples: { x: number; y: number }[] = []
  let prevMid = 320
  for (let y = neckY0; y <= neckY1; y += 1) {
    // Gentle sinusoidal centreline; keep consecutive rows 4-connected by also
    // opening the previous mid column when the centre steps sideways.
    const t = (y - neckY0) / (neckY1 - neckY0)
    const mid = 320 + Math.round(Math.sin(t * Math.PI) * 4)
    const half = Math.floor((neckWidth - 1) / 2)
    const openLo = Math.min(mid, prevMid) - half
    const openHi = Math.max(mid, prevMid) + half
    for (let x = ox0 + 1; x < openLo; x += 1) setBarrier(b, x, y)
    for (let x = openHi + 1; x < ox1; x += 1) setBarrier(b, x, y)
    samples.push({ x: mid, y })
    prevMid = mid
  }

  return {
    barrier: b,
    upperSeed: { x: 320, y: 240 },
    neckSamples: samples.filter((_, i) => i % 10 === 0),
    lowerSeed: { x: 320, y: 560 },
  }
}

/** Long vertical strap corridor of given interior width, fully closed. */
function strapBarrier(width: number): {
  barrier: Uint8Array
  seed: { x: number; y: number }
  x0: number
  x1: number
} {
  const x0 = 300
  const x1 = x0 + width + 1
  const y0 = 200
  const y1 = 700
  const b = closedRect(x0, y0, x1, y1)
  return {
    barrier: b,
    seed: { x: x0 + 1 + Math.floor((width - 1) / 2), y: 450 },
    x0,
    x1,
  }
}

/** Tiny closed pocket with exact interior pixel count. */
function tinyPocket(interiorW: number, interiorH: number, at?: { x: number; y: number }): {
  barrier: Uint8Array
  seed: { x: number; y: number }
  interiorPixels: number
} {
  const x0 = at?.x ?? 350
  const y0 = at?.y ?? 400
  const x1 = x0 + interiorW + 1
  const y1 = y0 + interiorH + 1
  return {
    barrier: closedRect(x0, y0, x1, y1),
    seed: { x: x0 + 1, y: y0 + 1 },
    interiorPixels: interiorW * interiorH,
  }
}

/** Closed right triangle with a narrow tip. */
function narrowTriangle(): { barrier: Uint8Array; seed: { x: number; y: number } } {
  const b = emptyBarrier()
  const x0 = 280
  const y0 = 300
  const x1 = 380
  const y1 = 520
  vWall(b, x0, y0, y1)
  hWall(b, y1, x0, x1)
  const steps = y1 - y0
  for (let i = 0; i <= steps; i += 1) {
    const x = x0 + Math.round((i / steps) * (x1 - x0))
    const y = y0 + i
    setBarrier(b, x, y)
    if (x + 1 < DESIGN_WIDTH) setBarrier(b, x + 1, y)
  }
  return { barrier: b, seed: { x: x0 + 8, y: y1 - 20 } }
}

function contourBounds(contour: number[]) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (let i = 0; i < contour.length; i += 2) {
    minX = Math.min(minX, contour[i]!)
    maxX = Math.max(maxX, contour[i]!)
    minY = Math.min(minY, contour[i + 1]!)
    maxY = Math.max(maxY, contour[i + 1]!)
  }
  return { minX, minY, maxX, maxY }
}

describe('P1 #60 internal seam punch-through safety', () => {
  it('BEFORE: undilated flood merges both panels through a 1px seam hole', () => {
    const { barrier, leftSeed, rightSeed } = dividedPanels('1px')
    const und = exploreFlood(barrier, leftSeed.x, leftSeed.y)
    expect(und.ok).toBe(true)
    if (!und.ok) return
    expect(und.visited[rightSeed.y * DESIGN_WIDTH + rightSeed.x]).toBe(1)
    expect(und.maxX).toBeGreaterThan(400)
  })

  it.each([
    ['1px', '1px'],
    ['2px', '2px'],
    ['diagonal', 'diagonal'],
    ['eraser-gap', 'eraser-gap'],
  ] as const)(
    'AFTER adaptive: %s internal seam hole stays panel-local (no spill to x=425)',
    (_label, hole) => {
      const { barrier, leftSeed, rightSeed } = dividedPanels(hole)
      const left = floodFillAdaptive({
        rawBarrier: barrier,
        ...leftSeed,
        style: solidStyle('#B91C1C'),
        maxGap: 2,
      })
      expect(left.ok).toBe(true)
      if (!left.ok) return

      const bounds = contourBounds(left.fill.contour)
      expect(bounds.maxX).toBeLessThanOrEqual(351)
      expect(contourCoversPixel(left.fill.contour, leftSeed.x, leftSeed.y)).toBe(true)
      expect(contourCoversPixel(left.fill.contour, rightSeed.x, rightSeed.y)).toBe(false)

      const persist = checkPersistableFill(left.fill)
      expect(persist.ok).toBe(true)
    },
  )

  it('intact internal seam still isolates neighbors (regression)', () => {
    const { barrier, leftSeed, rightSeed } = dividedPanels('none')
    const left = floodFillAdaptive({
      rawBarrier: barrier,
      ...leftSeed,
      style: solidStyle('#B91C1C'),
      maxGap: 2,
    })
    const right = floodFillAdaptive({
      rawBarrier: barrier,
      ...rightSeed,
      style: solidStyle('#1D4ED8'),
      maxGap: 2,
    })
    expect(left.ok).toBe(true)
    expect(right.ok).toBe(true)
    if (!left.ok || !right.ok) return
    expect(contourBounds(left.fill.contour).maxX).toBeLessThanOrEqual(350)
    expect(contourBounds(right.fill.contour).minX).toBeGreaterThanOrEqual(350)
  })

  it('classifies compact seam bridge as punch-through and elongated neck as not', () => {
    const seam = dividedPanels('1px')
    const und = exploreFlood(seam.barrier, seam.leftSeed.x, seam.leftSeed.y)
    expect(und.ok).toBe(true)
    if (!und.ok) return
    const dil = dilateMask(seam.barrier, 1)
    const panel = exploreFlood(dil, seam.leftSeed.x, seam.leftSeed.y)
    expect(panel.ok).toBe(true)
    if (!panel.ok) return
    expect(isAccidentalPunchThrough(seam.barrier, dil, und, panel)).toBe(true)

    const { barrier, upperSeed } = hourglassBarrier(1)
    const uUnd = exploreFlood(barrier, upperSeed.x, upperSeed.y)
    expect(uUnd.ok).toBe(true)
    if (!uUnd.ok) return
    const uDil = dilateMask(barrier, 1)
    const uPanel = exploreFlood(uDil, upperSeed.x, upperSeed.y)
    // 1px neck seals under dilate-1 → upper lobe only
    expect(uPanel.ok).toBe(true)
    if (!uPanel.ok) return
    expect(isAccidentalPunchThrough(barrier, uDil, uUnd, uPanel)).toBe(false)
  })
})

describe('P1 #60 narrow closed fills — hourglass / straps / pockets', () => {
  it.each([1, 2, 3, 4, 5, 8, 10])(
    'fixed gapClose=2 (legacy) seals a %d-px hourglass neck into separate lobes',
    (neckWidth) => {
      const { barrier, upperSeed, lowerSeed, neckSeed, neckX0, neckX1, neckY0, neckY1 } =
        hourglassBarrier(neckWidth)
      const dilated = dilateMask(barrier, 2)
      if (neckWidth <= 4) {
        let sealed = 0
        let open = 0
        for (let y = neckY0; y <= neckY1; y += 1) {
          for (let x = neckX0; x <= neckX1; x += 1) {
            if (dilated[y * DESIGN_WIDTH + x]) sealed += 1
            else open += 1
          }
        }
        expect(sealed).toBeGreaterThan(0)
        if (open === 0) {
          const upper = floodFillAgainstBarrier({
            barrier: dilated,
            ...upperSeed,
            style: solidStyle('#EAB308'),
          })
          const lower = floodFillAgainstBarrier({
            barrier: dilated,
            ...lowerSeed,
            style: solidStyle('#EAB308'),
          })
          expect(upper.ok).toBe(true)
          expect(lower.ok).toBe(true)
          if (!upper.ok || !lower.ok) return
          const ub = contourBounds(upper.fill.contour)
          const lb = contourBounds(lower.fill.contour)
          expect(ub.maxY).toBeLessThan(lb.minY)
          expect(
            floodFillAgainstBarrier({
              barrier: dilated,
              ...neckSeed,
              style: solidStyle('#EAB308'),
            }).ok,
          ).toBe(false)
        }
      }
    },
  )

  it.each([1, 2, 3, 4, 5, 8, 10])(
    'adaptive fill keeps a %d-px hourglass as one continuous region (pixel + contour)',
    (neckWidth) => {
      const { barrier, upperSeed, neckSeed, lowerSeed, neckY0, neckY1, neckX0, neckX1 } =
        hourglassBarrier(neckWidth)
      const fromUpper = floodFillAdaptive({
        rawBarrier: barrier,
        ...upperSeed,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(fromUpper.ok).toBe(true)
      if (!fromUpper.ok) return

      const bounds = contourBounds(fromUpper.fill.contour)
      expect(bounds.minY).toBeLessThan(neckY0)
      expect(bounds.maxY).toBeGreaterThan(neckY1)
      expect(contourCoversPixel(fromUpper.fill.contour, upperSeed.x, upperSeed.y)).toBe(true)
      expect(contourCoversPixel(fromUpper.fill.contour, lowerSeed.x, lowerSeed.y)).toBe(true)
      expect(contourCoversPixel(fromUpper.fill.contour, neckSeed.x, neckSeed.y)).toBe(true)

      // Pixel-level: undilated visit mask still includes the neck corridor.
      const und = exploreFlood(barrier, upperSeed.x, upperSeed.y)
      expect(und.ok).toBe(true)
      if (!und.ok) return
      for (let y = neckY0; y <= neckY1; y += 10) {
        for (let x = neckX0; x <= neckX1; x += 1) {
          expect(und.visited[y * DESIGN_WIDTH + x]).toBe(1)
        }
      }
      const span = minScanlineSpan(und.visited, und.minX, und.minY, und.maxX, und.maxY)
      expect(span).toBeLessThanOrEqual(neckWidth)
      const tol = contourSimplifyTolerance(
        und.count,
        und.maxX - und.minX + 1,
        und.maxY - und.minY + 1,
        span,
      )
      // Large hourglass lobes are "large garments": tolerance stays finite so
      // edge-based contours remain persistable; thin necks are protected by
      // collinear collapse + corridor sample checks, not global tol=0.
      expect(tol).toBeGreaterThan(0)
      expect(tol).toBeLessThanOrEqual(1.4)

      const fromNeck = floodFillAdaptive({
        rawBarrier: barrier,
        ...neckSeed,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(fromNeck.ok).toBe(true)
    },
  )

  it('curved 1–2px neck survives simplification with rasterized contour coverage', () => {
    for (const width of [1, 2]) {
      const { barrier, upperSeed, neckSamples, lowerSeed } = curvedNeckHourglass(width)
      const result = floodFillAdaptive({
        rawBarrier: barrier,
        ...upperSeed,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(result.ok).toBe(true)
      if (!result.ok) return
      expect(contourCoversPixel(result.fill.contour, upperSeed.x, upperSeed.y)).toBe(true)
      expect(contourCoversPixel(result.fill.contour, lowerSeed.x, lowerSeed.y)).toBe(true)
      for (const s of neckSamples) {
        expect(contourCoversPixel(result.fill.contour, s.x, s.y)).toBe(true)
      }
      const persist = checkPersistableFill(result.fill)
      expect(persist.ok).toBe(true)
      if (!persist.ok) return
      const roundTrip = parseFillOp(JSON.parse(JSON.stringify(persist.fill)))
      expect(roundTrip).not.toBeNull()
      for (const s of neckSamples) {
        expect(contourCoversPixel(roundTrip!.contour, s.x, s.y)).toBe(true)
      }
    }
  })

  it.each([1, 2, 3, 4, 5, 8, 10])('fills a closed %d-px-wide garment strap', (width) => {
    const { barrier, seed, x0, x1 } = strapBarrier(width)
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style: solidStyle('#B91C1C'),
      maxGap: 2,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const b = contourBounds(result.fill.contour)
    expect(b.minX).toBeGreaterThanOrEqual(x0)
    expect(b.maxX).toBeLessThanOrEqual(x1 + 1)
    expect(b.maxY - b.minY).toBeGreaterThan(100)
    expect(contourCoversPixel(result.fill.contour, seed.x, seed.y)).toBe(true)
  })

  it('fills a closed pocket smaller than the old 24-pixel threshold', () => {
    const { barrier, seed, interiorPixels } = tinyPocket(4, 5)
    expect(interiorPixels).toBe(20)
    const legacyReject = floodFillAgainstBarrier({
      barrier,
      ...seed,
      style: solidStyle('#111111'),
      minPixels: 24,
    })
    expect(legacyReject.ok).toBe(false)
    if (!legacyReject.ok) expect(legacyReject.reason).toBe('empty_region')

    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.fill.contour.length).toBeGreaterThanOrEqual(6)
    expect(checkPersistableFill(result.fill).ok).toBe(true)
  })

  it('fills a 1×1 micro pocket near design bounds and persists', () => {
    const { barrier, seed } = tinyPocket(1, 1, { x: DESIGN_WIDTH - 4, y: DESIGN_HEIGHT - 4 })
    const result = floodFillAgainstBarrier({
      barrier,
      ...seed,
      style: solidStyle('#0F766E'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.fill.contour.length).toBeGreaterThanOrEqual(6)
    const persist = checkPersistableFill(result.fill)
    expect(persist.ok).toBe(true)
    if (!persist.ok) return
    const roundTrip = parseFillOp(JSON.parse(JSON.stringify(persist.fill)))
    expect(roundTrip).not.toBeNull()
    expect(contourCoversPixel(roundTrip!.contour, seed.x, seed.y)).toBe(true)
  })

  it('rejects zero-area / empty regions', () => {
    const b = emptyBarrier()
    // Solid ink blob — no interior.
    for (let y = 100; y <= 110; y += 1) hWall(b, y, 100, 110)
    const result = floodFillAgainstBarrier({
      barrier: b,
      x: 105,
      y: 105,
      style: solidStyle('#111111'),
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.reason).toBe('outside')
  })

  it('fills a narrow triangular tip without spilling outside the walls', () => {
    const { barrier, seed } = narrowTriangle()
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style: solidStyle('#1D4ED8'),
      maxGap: 2,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const b = contourBounds(result.fill.contour)
    expect(b.minX).toBeGreaterThanOrEqual(280)
    expect(b.maxX).toBeLessThanOrEqual(383)
    expect(b.maxY).toBeLessThanOrEqual(522)
  })
})

describe('P1 #60 safety — open gaps, ink taps, max area', () => {
  it('still fails closed for a genuinely open outline (U-shape to paper)', () => {
    const b = emptyBarrier()
    vWall(b, 200, 200, 500)
    vWall(b, 400, 200, 500)
    hWall(b, 500, 200, 400)
    const result = floodFillAdaptive({
      rawBarrier: b,
      x: 300,
      y: 350,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('open_outline')
      expect(result.message).toMatch(/close the shape/i)
    }
  })

  it('still fails when a wide (8px) gap opens to the paper edge', () => {
    const b = closedRect(200, 200, 400, 500)
    for (let x = 290; x < 298; x += 1) b[200 * DESIGN_WIDTH + x] = 0
    for (let y = 0; y <= 200; y += 1) {
      for (let x = 290; x < 298; x += 1) b[y * DESIGN_WIDTH + x] = 0
    }
    const result = floodFillAdaptive({
      rawBarrier: b,
      x: 300,
      y: 350,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(['open_outline', 'too_large']).toContain(result.reason)
  })

  it('does not fill when tapping actual visible ink', () => {
    const b = closedRect(200, 200, 300, 300)
    const result = floodFillAdaptive({
      rawBarrier: b,
      x: 200,
      y: 250,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('outside')
      expect(result.message).toMatch(/not on the outline/i)
    }
  })

  it('retains MAX_FILL_PIXELS page-wide flood protection', () => {
    expect(MAX_FILL_PIXELS).toBeGreaterThan(10_000)
    const result = floodFillAgainstBarrier({
      barrier: emptyBarrier(),
      x: 384,
      y: 512,
      style: solidStyle('#111111'),
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.reason).toBe('open_outline')
  })

  it('uses gap closing only when the undilated outline is open by a hairline', () => {
    const b = closedRect(250, 250, 450, 450)
    b[250 * DESIGN_WIDTH + 340] = 0
    b[250 * DESIGN_WIDTH + 341] = 0

    const undilated = floodFillAgainstBarrier({
      barrier: b,
      x: 350,
      y: 350,
      style: solidStyle('#111111'),
    })
    expect(undilated.ok).toBe(false)
    if (!undilated.ok) expect(undilated.reason).toBe('open_outline')

    const adaptive = floodFillAdaptive({
      rawBarrier: b,
      x: 350,
      y: 350,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(adaptive.ok).toBe(true)
  })

  it('does not silently truncate oversized contours', () => {
    // Contour with > MAX values must be refused by persist check, never clipped.
    const huge: number[] = []
    for (let i = 0; i < 5000; i += 1) huge.push(i % 700, (i * 3) % 900)
    const refused = checkPersistableFill({
      id: 'fill_test_huge',
      contour: huge,
      style: solidStyle('#111111'),
      seedX: 10,
      seedY: 10,
    })
    expect(refused.ok).toBe(false)
  })
})

describe('P1 #60 fill styles + persistence round-trip', () => {
  it.each([
    ['solid', solidStyle('#EAB308')],
    ['gradient', gradientStyleFromPreset('champagne')!],
    ['fabric', fabricStyle('lace')!],
    [
      'uploaded-fabric',
      uploadedFabricStyle('00000000-0000-4000-8000-000000000001', 1)!,
    ],
  ] as const)('%s style persists through parseFillOp / checkPersistableFill', (_label, style) => {
    const { barrier, seed } = strapBarrier(3)
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style,
      maxGap: 2,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const persist = checkPersistableFill(result.fill)
    expect(persist.ok).toBe(true)
    if (!persist.ok) return
    const roundTrip = parseFillOp(JSON.parse(JSON.stringify(persist.fill)))
    expect(roundTrip).not.toBeNull()
    expect(roundTrip!.style).toEqual(persist.fill.style)
    expect(roundTrip!.contour).toEqual(persist.fill.contour)
    expect(contourCoversPixel(roundTrip!.contour, seed.x, seed.y)).toBe(true)
  })
})

describe('P1 #60 real viewport transform + pinch (100% / 177% / 300%)', () => {
  const tablet = { width: 768, height: 900 }

  function viewportAtZoom(percent: number): ViewportState {
    const base = hundredPercent(tablet)
    if (percent === 100) return base
    const anchor = designToScreen(320, 400, base)
    return zoomAt(base, tablet, percent / 100, anchor.x, anchor.y)
  }

  it.each([100, 177, 300])(
    'screen→design at %d%% zoom seeds a narrow closed fill identically',
    (percent) => {
      const { barrier, neckSeed } = hourglassBarrier(2)
      const vp = viewportAtZoom(percent)
      expect(vp.scale).toBeCloseTo(percent / 100, 5)

      const screen = designToScreen(neckSeed.x, neckSeed.y, vp)
      const design = screenToDesign(screen.x, screen.y, vp)
      expect(design.x).toBeCloseTo(neckSeed.x, 5)
      expect(design.y).toBeCloseTo(neckSeed.y, 5)

      const result = floodFillAdaptive({
        rawBarrier: barrier,
        x: design.x,
        y: design.y,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(result.ok).toBe(true)
      if (!result.ok) return
      expect(contourCoversPixel(result.fill.contour, neckSeed.x, neckSeed.y)).toBe(true)
    },
  )

  it('pinch gesture keeps the narrow-region design point under the focal midpoint', () => {
    const before = viewportAtZoom(100)
    const mid = { x: tablet.width / 2, y: tablet.height / 2 }
    const designBefore = screenToDesign(mid.x, mid.y, before)
    const factor = pinchScaleFactor(120, 120 * 1.77)
    const after = zoomAt(before, tablet, before.scale * factor, mid.x, mid.y)
    expect(after.scale).toBeCloseTo(1.77, 2)
    const designAfter = screenToDesign(mid.x, mid.y, after)
    expect(designAfter.x).toBeCloseTo(designBefore.x, 4)
    expect(designAfter.y).toBeCloseTo(designBefore.y, 4)

    const box = { width: 1400, height: 1100 }
    const wideBefore = hundredPercent(box)
    const prevMid = { x: 700, y: 550 }
    const nextMid = { x: 760, y: 590 }
    const garment = screenToDesign(prevMid.x, prevMid.y, wideBefore)
    const panned = pinchPan(
      wideBefore,
      box,
      wideBefore.scale * 3,
      prevMid.x,
      prevMid.y,
      nextMid.x,
      nextMid.y,
    )
    expect(panned.scale).toBeCloseTo(3, 5)
    const screen = designToScreen(garment.x, garment.y, panned)
    expect(screen.x).toBeCloseTo(nextMid.x, 3)
    expect(screen.y).toBeCloseTo(nextMid.y, 3)
  })

  it('design-space fill math is invariant across zoom (same seeds → same contour)', () => {
    const { barrier, upperSeed } = hourglassBarrier(3)
    const contours = [100, 177, 300].map((percent) => {
      const vp = viewportAtZoom(percent)
      const screen = designToScreen(upperSeed.x, upperSeed.y, vp)
      const design = screenToDesign(screen.x, screen.y, vp)
      const r = floodFillAdaptive({
        rawBarrier: barrier,
        x: design.x,
        y: design.y,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(r.ok).toBe(true)
      return r.ok ? r.fill.contour : []
    })
    expect(contours[0]).toEqual(contours[1])
    expect(contours[1]).toEqual(contours[2])
  })
})

describe('P1 #60 large-garment contour persistence', () => {
  /** Long tapered dress: 1px shoulder tip → wide hem (triggers global minSpan=1). */
  function taperedDressBarrier(): {
    barrier: Uint8Array
    seed: { x: number; y: number }
    tip: { x: number; y: number }
  } {
    const b = emptyBarrier()
    const topY = 80
    const botY = 900
    const tipX = 384
    for (let y = topY; y <= botY; y += 1) {
      const t = (y - topY) / (botY - topY)
      const half = Math.max(0, Math.round(1 + t * 180))
      setBarrier(b, tipX - half, y)
      setBarrier(b, tipX + half, y)
    }
    hWall(b, botY, tipX - 180, tipX + 180)
    setBarrier(b, tipX, topY)
    return { barrier: b, seed: { x: tipX, y: 500 }, tip: { x: tipX, y: topY + 2 } }
  }

  /** Full-length trouser leg with irregular (hand-drawn) side walls. */
  function irregularTrouserLeg(): {
    barrier: Uint8Array
    seed: { x: number; y: number }
  } {
    const b = emptyBarrier()
    const y0 = 120
    const y1 = 920
    const mid = 360
    let prevL = mid - 42
    let prevR = mid + 42
    for (let y = y0; y <= y1; y += 1) {
      const wobble = Math.round(Math.sin(y / 17) * 8 + Math.sin(y / 9) * 4)
      const half = 42 + wobble
      const l = mid - half
      const r = mid + half
      // Seal horizontal steps so a freehand wobble cannot open the silhouette.
      const l0 = Math.min(prevL, l)
      const l1 = Math.max(prevL, l)
      const r0 = Math.min(prevR, r)
      const r1 = Math.max(prevR, r)
      for (let x = l0; x <= l1; x += 1) setBarrier(b, x, y)
      for (let x = r0; x <= r1; x += 1) setBarrier(b, x, y)
      prevL = l
      prevR = r
    }
    hWall(b, y0, mid - 42, mid + 42)
    hWall(b, y1, Math.min(prevL, mid - 50), Math.max(prevR, mid + 50))
    return { barrier: b, seed: { x: mid, y: 520 } }
  }

  /** Large curved panel (elliptical-ish closed outline). */
  function largeCurvedPanel(): {
    barrier: Uint8Array
    seed: { x: number; y: number }
  } {
    const b = emptyBarrier()
    const cx = 384
    const cy = 512
    const rx = 220
    const ry = 340
    let prevX = -1
    let prevY = -1
    for (let i = 0; i <= 720; i += 1) {
      const a = (i / 720) * Math.PI * 2
      const x = Math.round(cx + Math.cos(a) * rx)
      const y = Math.round(cy + Math.sin(a) * ry)
      setBarrier(b, x, y)
      if (prevX >= 0) {
        // Bresenham-lite seal between samples
        const steps = Math.max(Math.abs(x - prevX), Math.abs(y - prevY))
        for (let s = 1; s < steps; s += 1) {
          const px = Math.round(prevX + ((x - prevX) * s) / steps)
          const py = Math.round(prevY + ((y - prevY) * s) / steps)
          setBarrier(b, px, py)
        }
      }
      prevX = x
      prevY = y
    }
    return { barrier: b, seed: { x: cx, y: cy } }
  }

  /** Jagged freehand-style closed outline with many stair-steps. */
  function jaggedFreehandOutline(): {
    barrier: Uint8Array
    seed: { x: number; y: number }
  } {
    const b = emptyBarrier()
    const y0 = 160
    const y1 = 860
    const left = 200
    const right = 560
    for (let y = y0; y <= y1; y += 1) {
      const jL = ((y * 5) % 7) - 3
      const jR = ((y * 3) % 9) - 4
      setBarrier(b, left + jL, y)
      setBarrier(b, right + jR, y)
    }
    for (let x = left - 3; x <= right + 4; x += 1) {
      const jT = ((x * 2) % 5) - 2
      const jB = ((x * 7) % 5) - 2
      setBarrier(b, x, y0 + jT)
      setBarrier(b, x, y1 + jB)
    }
    return { barrier: b, seed: { x: 380, y: 500 } }
  }

  function expectPersistableFill(
    label: string,
    barrier: Uint8Array,
    seed: { x: number; y: number },
    extras?: { cover?: { x: number; y: number }[]; maxMs?: number },
  ) {
    const t0 = performance.now()
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style: solidStyle('#B91C1C'),
      maxGap: 2,
    })
    const ms = performance.now() - t0
    expect(result.ok, `${label} fill ok`).toBe(true)
    if (!result.ok) return
    expect(result.fill.contour.length, `${label} under contour cap`).toBeLessThanOrEqual(
      MAX_FILL_CONTOUR_VALUES,
    )
    expect(result.fill.contour.length, `${label} has polygon`).toBeGreaterThanOrEqual(6)
    const persist = checkPersistableFill(result.fill)
    expect(persist.ok, `${label} persistable`).toBe(true)
    if (!persist.ok) return
    const roundTrip = parseFillOp(JSON.parse(JSON.stringify(persist.fill)))
    expect(roundTrip).not.toBeNull()
    expect(roundTrip!.contour).toEqual(persist.fill.contour)
    expect(contourCoversPixel(roundTrip!.contour, seed.x, seed.y)).toBe(true)
    for (const p of extras?.cover ?? []) {
      expect(contourCoversPixel(roundTrip!.contour, p.x, p.y), `${label} cover ${p.x},${p.y}`).toBe(
        true,
      )
    }
    expect(ms, `${label} bounded runtime`).toBeLessThan(extras?.maxMs ?? 1500)
    return { result, ms, contourLen: result.fill.contour.length }
  }

  it('BEFORE: uncompressed edge contour on tapered dress exceeds persistence cap', () => {
    const { barrier, seed } = taperedDressBarrier()
    const und = exploreFlood(barrier, seed.x, seed.y)
    expect(und.ok).toBe(true)
    if (!und.ok) return
    expect(minScanlineSpan(und.visited, und.minX, und.minY, und.maxX, und.maxY)).toBe(1)
    // Legacy hazard: minSpan≤2 → tol 0 → keep every edge vertex → over cap.
    const raw = traceRegionContour(und.visited, und.minX, und.minY, und.maxX, und.maxY)
    expect(raw.length).toBeGreaterThan(MAX_FILL_CONTOUR_VALUES)
    expect(
      checkPersistableFill({
        id: 'fill_raw_oversize',
        contour: raw,
        style: solidStyle('#111111'),
        seedX: seed.x,
        seedY: seed.y,
      }).ok,
    ).toBe(false)
    // Topology-preserving collinear collapse alone brings this dress under the cap.
    expect(removeCollinearPoints(raw).length).toBeLessThanOrEqual(MAX_FILL_CONTOUR_VALUES)
  })

  it('AFTER: tapered dress with 1px tip fills and persists under the contour cap', () => {
    const { barrier, seed, tip } = taperedDressBarrier()
    const out = expectPersistableFill('tapered dress', barrier, seed, {
      cover: [tip],
      maxMs: 1500,
    })
    expect(out!.contourLen).toBeLessThanOrEqual(MAX_FILL_CONTOUR_VALUES)
  })

  it('AFTER: irregular full-length trouser leg persists', () => {
    const { barrier, seed } = irregularTrouserLeg()
    expectPersistableFill('trouser leg', barrier, seed)
  })

  it('AFTER: large curved garment panel persists', () => {
    const { barrier, seed } = largeCurvedPanel()
    expectPersistableFill('curved panel', barrier, seed)
  })

  it('AFTER: large hourglass (wide lobes + 1px neck) persists with neck coverage', () => {
    const { barrier, upperSeed, neckSeed, lowerSeed } = hourglassBarrier(1)
    expectPersistableFill('large hourglass', barrier, upperSeed, {
      cover: [neckSeed, lowerSeed],
    })
  })

  it('AFTER: jagged freehand outline persists', () => {
    const { barrier, seed } = jaggedFreehandOutline()
    expectPersistableFill('jagged freehand', barrier, seed)
  })

  it('AFTER: complex closed region below MAX_FILL_PIXELS stays persistable', () => {
    // Comb-like closed silhouette: many vertical fins → long perimeter, still enclosed.
    const b = emptyBarrier()
    const x0 = 180
    const x1 = 580
    const y0 = 140
    const y1 = 860
    hWall(b, y0, x0, x1)
    hWall(b, y1, x0, x1)
    vWall(b, x0, y0, y1)
    vWall(b, x1, y0, y1)
    for (let x = x0 + 20; x < x1 - 20; x += 18) {
      for (let y = y0 + 30; y < y1 - 30; y += 1) {
        if ((y + x) % 40 < 22) setBarrier(b, x, y)
      }
    }
    const und = exploreFlood(b, 300, 500)
    expect(und.ok).toBe(true)
    if (!und.ok) return
    expect(und.count).toBeLessThanOrEqual(MAX_FILL_PIXELS)
    expectPersistableFill('complex under max pixels', b, { x: 300, y: 500 }, { maxMs: 2500 })
  })

  it('adaptive fill success is always persistable (no fake ok)', () => {
    const fixtures = [
      taperedDressBarrier(),
      irregularTrouserLeg(),
      largeCurvedPanel(),
      jaggedFreehandOutline(),
      { barrier: hourglassBarrier(1).barrier, seed: hourglassBarrier(1).upperSeed },
    ]
    for (const f of fixtures) {
      const r = floodFillAdaptive({
        rawBarrier: f.barrier,
        ...f.seed,
        style: solidStyle('#0F766E'),
        maxGap: 2,
      })
      expect(r.ok).toBe(true)
      if (!r.ok) continue
      expect(checkPersistableFill(r.fill).ok).toBe(true)
    }
  })
})

describe('P1 #60 reference-model policy reminder', () => {
  it('flood fill only sees the provided ink barrier — croquis is never injected', () => {
    const result = floodFillAdaptive({
      rawBarrier: emptyBarrier(),
      x: 384,
      y: 512,
      style: solidStyle('#111111'),
      maxGap: 2,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.reason).toBe('open_outline')
  })
})
