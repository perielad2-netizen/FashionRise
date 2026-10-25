/**
 * P1 #60 — narrow closed-shape fill regressions (synthetic barriers only).
 * No canvas, no user artwork, no paid AI.
 */
import { describe, expect, it } from 'vitest'
import {
  dilateMask,
  floodFillAdaptive,
  floodFillAgainstBarrier,
  MAX_FILL_PIXELS,
} from '@/lib/floodFill'
import { checkPersistableFill, parseFillOp, solidStyle } from '@/lib/fills'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

function emptyBarrier(): Uint8Array {
  return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
}

function setBarrier(barrier: Uint8Array, x: number, y: number) {
  barrier[y * DESIGN_WIDTH + x] = 1
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
 * Hourglass: two wide lobes connected by a vertical neck of `neckWidth` open
 * interior pixels. Entire silhouette is a single closed outline.
 *
 * Geometry (design space):
 *   Outer box: [ox0,oy0]–[ox1,oy1]
 *   Neck open x-range centered at midX with given width
 *   Neck y-range: [neckY0, neckY1]
 *   Side walls fill the lobe flanks so the only passage is the neck.
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
  // Outer rectangle
  hWall(b, oy0, ox0, ox1)
  hWall(b, oy1, ox0, ox1)
  vWall(b, ox0, oy0, oy1)
  vWall(b, ox1, oy0, oy1)

  // Pinch walls: fill left/right of neck between lobes so only the neck is open.
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

/** Long vertical strap corridor of given interior width, fully closed. */
function strapBarrier(width: number): {
  barrier: Uint8Array
  seed: { x: number; y: number }
  x0: number
  x1: number
} {
  const x0 = 300
  const x1 = x0 + width + 1 // walls at x0 and x1, interior width = width
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
function tinyPocket(interiorW: number, interiorH: number): {
  barrier: Uint8Array
  seed: { x: number; y: number }
  interiorPixels: number
} {
  const x0 = 350
  const y0 = 400
  const x1 = x0 + interiorW + 1
  const y1 = y0 + interiorH + 1
  return {
    barrier: closedRect(x0, y0, x1, y1),
    seed: { x: x0 + 1, y: y0 + 1 },
    interiorPixels: interiorW * interiorH,
  }
}

/** Closed right triangle with a narrow tip (hypotenuse + two legs). */
function narrowTriangle(): { barrier: Uint8Array; seed: { x: number; y: number } } {
  const b = emptyBarrier()
  const x0 = 280
  const y0 = 300
  const x1 = 380
  const y1 = 520
  // Vertical leg
  vWall(b, x0, y0, y1)
  // Base
  hWall(b, y1, x0, x1)
  // Hypotenuse from (x0,y0) to (x1,y1)
  const steps = y1 - y0
  for (let i = 0; i <= steps; i += 1) {
    const x = x0 + Math.round((i / steps) * (x1 - x0))
    const y = y0 + i
    setBarrier(b, x, y)
    // thicken one px so raster is sealed
    if (x + 1 < DESIGN_WIDTH) setBarrier(b, x + 1, y)
  }
  return { barrier: b, seed: { x: x0 + 8, y: y1 - 20 } }
}

/** Point-in-polygon (ray cast) for flat [x,y,...] contours. */
function pointInContour(contour: number[], x: number, y: number): boolean {
  let inside = false
  for (let i = 0, j = contour.length - 2; i < contour.length; i += 2) {
    const xi = contour[i]!
    const yi = contour[i + 1]!
    const xj = contour[j]!
    const yj = contour[j + 1]!
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + Number.EPSILON) + xi
    if (intersect) inside = !inside
    j = i
  }
  return inside
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

describe('P1 #60 narrow closed fills — before/after dilation behavior', () => {
  it.each([1, 2, 3, 4, 5, 8, 10])(
    'fixed gapClose=2 (legacy) seals a %d-px hourglass neck into separate lobes',
    (neckWidth) => {
      const { barrier, upperSeed, lowerSeed, neckSeed, neckX0, neckX1, neckY0, neckY1 } =
        hourglassBarrier(neckWidth)
      const dilated = dilateMask(barrier, 2)
      // For necks ≤ 4px, square dilate-2 from both flanks meets/overlaps.
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
        // Legacy single-pass with gap=2 cannot treat upper+lower as one region
        // when the neck is fully sealed.
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
          // Neck seed is on synthetic barrier.
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
    'adaptive fill keeps a %d-px hourglass as one continuous region',
    (neckWidth) => {
      const { barrier, upperSeed, neckSeed, lowerSeed, neckY0, neckY1 } =
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
      // Contour spans both lobes through the neck.
      expect(bounds.minY).toBeLessThan(neckY0)
      expect(bounds.maxY).toBeGreaterThan(neckY1)
      expect(pointInContour(fromUpper.fill.contour, upperSeed.x, upperSeed.y)).toBe(true)
      expect(pointInContour(fromUpper.fill.contour, lowerSeed.x, lowerSeed.y)).toBe(true)
      // Neck corridor remains represented (seed inside polygon or near midline).
      expect(pointInContour(fromUpper.fill.contour, neckSeed.x, neckSeed.y)).toBe(true)

      const fromNeck = floodFillAdaptive({
        rawBarrier: barrier,
        ...neckSeed,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
      expect(fromNeck.ok).toBe(true)
    },
  )
})

describe('P1 #60 straps, tiny pockets, triangles', () => {
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
    expect(b.maxX).toBeLessThanOrEqual(x1)
    expect(b.maxY - b.minY).toBeGreaterThan(100)
  })

  it('fills a closed pocket smaller than the old 24-pixel threshold', () => {
    // 4×5 = 20 interior pixels (< 24)
    const { barrier, seed, interiorPixels } = tinyPocket(4, 5)
    expect(interiorPixels).toBe(20)
    expect(interiorPixels).toBeLessThan(24)

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
    const persist = checkPersistableFill(result.fill)
    expect(persist.ok).toBe(true)
  })

  it('fills a 1×1 micro pocket via bbox contour fallback', () => {
    const { barrier, seed } = tinyPocket(1, 1)
    const result = floodFillAgainstBarrier({
      barrier,
      ...seed,
      style: solidStyle('#0F766E'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.fill.contour.length).toBeGreaterThanOrEqual(6)
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
    expect(b.maxX).toBeLessThanOrEqual(382)
    expect(b.maxY).toBeLessThanOrEqual(521)
  })
})

describe('P1 #60 safety — open gaps, ink taps, neighbors, max area', () => {
  it('still fails closed for a genuinely open outline (U-shape to paper)', () => {
    const b = emptyBarrier()
    // Three sides only — top permanently open; dilation cannot invent a lid.
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

  it('does not bleed across a shared seam into a neighboring region', () => {
    const b = emptyBarrier()
    // Two rooms side by side with a shared wall.
    hWall(b, 200, 200, 500)
    hWall(b, 500, 200, 500)
    vWall(b, 200, 200, 500)
    vWall(b, 350, 200, 500)
    vWall(b, 500, 200, 500)

    const left = floodFillAdaptive({
      rawBarrier: b,
      x: 275,
      y: 350,
      style: solidStyle('#B91C1C'),
      maxGap: 2,
    })
    const right = floodFillAdaptive({
      rawBarrier: b,
      x: 425,
      y: 350,
      style: solidStyle('#1D4ED8'),
      maxGap: 2,
    })
    expect(left.ok).toBe(true)
    expect(right.ok).toBe(true)
    if (!left.ok || !right.ok) return
    const lb = contourBounds(left.fill.contour)
    const rb = contourBounds(right.fill.contour)
    expect(lb.maxX).toBeLessThanOrEqual(350)
    expect(rb.minX).toBeGreaterThanOrEqual(350)
  })

  it('retains MAX_FILL_PIXELS page-wide flood protection', () => {
    expect(MAX_FILL_PIXELS).toBeGreaterThan(10_000)
    // Empty barrier from centre escapes to edge → open_outline (not a huge fill).
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
    // Closed rect with a 2px gap in the top — sealed by maxGap=2, not by gap=0.
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
})

describe('P1 #60 persistence, zoom independence, contour fidelity', () => {
  it('saved/reopened contours retain thin strap geometry', () => {
    const { barrier, seed } = strapBarrier(3)
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...seed,
      style: solidStyle('#EAB308'),
      maxGap: 2,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const persist = checkPersistableFill(result.fill)
    expect(persist.ok).toBe(true)
    if (!persist.ok) return
    const roundTrip = parseFillOp(JSON.parse(JSON.stringify(persist.fill)))
    expect(roundTrip).not.toBeNull()
    expect(roundTrip!.contour).toEqual(persist.fill.contour)
    const b = contourBounds(roundTrip!.contour)
    expect(b.maxX - b.minX).toBeLessThanOrEqual(6)
  })

  it('is zoom-independent (design-space seeds only — 100% / 177% / 300%)', () => {
    const { barrier, upperSeed } = hourglassBarrier(3)
    const results = [1, 1.77, 3].map((zoom) => {
      // Viewport zoom must not alter design-space fill math.
      void zoom
      return floodFillAdaptive({
        rawBarrier: barrier,
        ...upperSeed,
        style: solidStyle('#EAB308'),
        maxGap: 2,
      })
    })
    expect(results.every((r) => r.ok)).toBe(true)
    const contours = results.map((r) => (r.ok ? r.fill.contour : []))
    expect(contours[0]).toEqual(contours[1])
    expect(contours[1]).toEqual(contours[2])
  })

  it('adaptive tolerance keeps neck points for narrow hourglass contours', () => {
    const { barrier, upperSeed, neckSeed } = hourglassBarrier(2)
    const result = floodFillAdaptive({
      rawBarrier: barrier,
      ...upperSeed,
      style: solidStyle('#EAB308'),
      maxGap: 0,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(pointInContour(result.fill.contour, neckSeed.x, neckSeed.y)).toBe(true)
  })
})

describe('P1 #60 reference-model policy reminder', () => {
  it('flood fill only sees the provided ink barrier — croquis is never injected', () => {
    // Empty barrier = blank paper (no croquis raster). Fill must fail open, not
    // invent a figure-shaped enclosure from a reference model.
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
