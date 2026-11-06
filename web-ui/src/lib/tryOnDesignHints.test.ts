import { describe, expect, it, beforeEach } from 'vitest'
import {
  buildTryOnDesignHints,
  detectBilateralSleevesFromFills,
  detectFootwearInk,
  detectOpenNecklineFromFills,
  detectSeparateTopBottom,
  detectTrouserLegFills,
  liveArtworkYSpan,
  sanitizeFabricHintText,
} from '@/lib/tryOnDesignHints'
import { clearFabricPromptCache, rememberFabricPromptShort } from '@/lib/fabricPromptCache'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'

function stroke(partial: Partial<Stroke> & { points: number[] }): Stroke {
  return {
    id: partial.id ?? 's1',
    tool: partial.tool ?? 'draw',
    color: partial.color ?? '#FF69B4',
    size: partial.size ?? 4,
    opacity: partial.opacity ?? 1,
    points: partial.points,
  }
}

describe('buildTryOnDesignHints', () => {
  it('emits color, print topology, and upper accessory hints', () => {
    const fills: FillOp[] = [
      {
        id: 'f1',
        contour: [10, 20, 40, 20, 40, 60, 10, 60],
        seedX: 20,
        seedY: 30,
        style: { kind: 'solid', color: '#FF69B4' },
      },
    ]
    const strokes: Stroke[] = [
      stroke({ id: 'hat', points: [100, 40, 0.5, 140, 60, 0.5], color: '#222222' }),
    ]
    const hints = buildTryOnDesignHints({ strokes, fills })
    expect(hints.some((h) => h.includes('#FF69B4'))).toBe(true)
    expect(hints.some((h) => /checkerboard|print topology/i.test(h))).toBe(true)
    expect(hints.some((h) => /hat\/cap/i.test(h))).toBe(true)
    expect(hints.length).toBeLessThanOrEqual(8)
  })

  it('mentions fabric presets when used', () => {
    const fills: FillOp[] = [
      {
        id: 'f2',
        contour: [12, 40, 80, 40, 80, 120, 12, 120],
        seedX: 40,
        seedY: 70,
        style: { kind: 'fabric', fabricId: 'floral' },
      },
    ]
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /Floral repeating fabric fill/i.test(h))).toBe(true)
  })

  it('adds jumpsuit/narrow-leg hints when two lower fills are clear', () => {
    const fills: FillOp[] = [
      {
        id: 'bodice',
        contour: [300, 80, 460, 80, 460, 420, 300, 420],
        seedX: 380,
        seedY: 240,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'leftLeg',
        contour: [300, 500, 360, 500, 360, 900, 300, 900],
        seedX: 330,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'rightLeg',
        contour: [400, 500, 460, 500, 460, 900, 400, 900],
        seedX: 430,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
    ]
    const detected = detectTrouserLegFills(fills)
    expect(detected.looksLikeTrousers).toBe(true)
    expect(detected.looksLikeJumpsuit).toBe(true)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /jumpsuit/i.test(h))).toBe(true)
    expect(hints.some((h) => /separate/i.test(h))).toBe(true)
    expect(hints.some((h) => /skirt panel/i.test(h))).toBe(true)
  })

  it('does not inject trousers hints for a dress/skirt fill', () => {
    const fills: FillOp[] = [
      {
        id: 'dress',
        contour: [200, 100, 560, 100, 600, 900, 160, 900],
        seedX: 380,
        seedY: 500,
        style: { kind: 'solid', color: '#B91C1C' },
      },
    ]
    expect(detectTrouserLegFills(fills).looksLikeTrousers).toBe(false)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /jumpsuit|pant legs/i.test(h) || /^garment type: trousers/i.test(h))).toBe(
      false,
    )
    expect(hints.some((h) => /continuous one-piece|do not leave jeans/i.test(h))).toBe(true)
  })

  it('ignores foot-band stroke crumbs after shoe erase for try-on completeness span', () => {
    const fills: FillOp[] = [
      {
        id: 'swim',
        contour: [320, 140, 460, 140, 500, 620, 280, 620],
        seedX: 380,
        seedY: 360,
        style: { kind: 'solid', color: '#0E7490' },
      },
    ]
    // Leftover shoe outline crumbs after erase (foot band only).
    const crumbs: Stroke[] = [
      stroke({
        id: 'shoe-crumb',
        color: '#111111',
        points: [300, 920, 0.5, 320, 940, 0.5, 310, 960, 0.5],
      }),
    ]
    const raw = liveArtworkYSpan({ strokes: crumbs, fills })
    const gated = liveArtworkYSpan({
      strokes: crumbs,
      fills,
      forTryOnCompleteness: true,
    })
    expect(raw?.maxY).toBeGreaterThan(900)
    expect(gated?.maxY).toBeLessThanOrEqual(620 + 24)
  })

  it('ignores erased shoe fills + full shoe strokes for try-on completeness (back croquis)', () => {
    // Swimsuit body + black shoe fills still in the document after ink-erase
    // punched them out of capture alpha (owner: "deleted everything, no leftovers").
    const fills: FillOp[] = [
      {
        id: 'swim',
        contour: [320, 140, 460, 140, 500, 620, 280, 620],
        seedX: 380,
        seedY: 360,
        style: { kind: 'solid', color: '#0E7490' },
      },
      {
        id: 'shoeL',
        contour: [280, 900, 340, 900, 340, 1000, 280, 1000],
        seedX: 310,
        seedY: 950,
        style: { kind: 'solid', color: '#111111' },
      },
      {
        id: 'shoeR',
        contour: [420, 900, 480, 900, 480, 1000, 420, 1000],
        seedX: 450,
        seedY: 950,
        style: { kind: 'solid', color: '#111111' },
      },
    ]
    const shoeStrokes: Stroke[] = [
      stroke({
        id: 'shoe-outline',
        color: '#111111',
        // Full shoe stroke from ankle into foot band — not a tiny crumb.
        points: [300, 860, 0.5, 330, 940, 0.5, 310, 990, 0.5],
      }),
    ]
    const raw = liveArtworkYSpan({ strokes: shoeStrokes, fills })
    const gated = liveArtworkYSpan({
      strokes: shoeStrokes,
      fills,
      forTryOnCompleteness: true,
    })
    expect(raw?.maxY).toBeGreaterThanOrEqual(990)
    // Shoe fills must not defeat high-cut body span (prior fix only dropped crumbs).
    expect(gated?.maxY).toBeLessThanOrEqual(620 + 24)
  })

  it('injects one-piece coverage hints for swimsuit-like fills (not trousers)', () => {
    const fills: FillOp[] = [
      {
        id: 'swim',
        // Torso → upper-thigh hem on the 1024 design plane (owner one-piece case).
        contour: [320, 140, 460, 140, 500, 620, 280, 620],
        seedX: 380,
        seedY: 360,
        style: { kind: 'solid', color: '#0E7490' },
      },
    ]
    expect(detectTrouserLegFills(fills).looksLikeTrousers).toBe(false)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /continuous one-piece/i.test(h))).toBe(true)
    expect(hints.some((h) => /do not leave jeans/i.test(h))).toBe(true)
    expect(hints.some((h) => /bare feet|remove photo boots/i.test(h))).toBe(true)
    expect(hints.some((h) => /high-cut one-piece|do not lengthen into a dress/i.test(h))).toBe(true)
  })

  it('detects dark footwear ink near the feet (#184)', () => {
    const strokes: Stroke[] = [
      stroke({
        id: 'shoe',
        color: '#111111',
        points: [300, 900, 0.5, 340, 940, 0.5, 360, 980, 0.5],
      }),
    ]
    expect(detectFootwearInk(strokes, [])).toBe(true)
    const hints = buildTryOnDesignHints({ strokes, fills: [] })
    expect(hints.some((h) => /footwear|shoes|boots/i.test(h))).toBe(true)
  })

  it('detects filled black shoes near the feet (not only outline strokes)', () => {
    const fills: FillOp[] = [
      {
        id: 'suit',
        contour: [220, 180, 520, 180, 500, 720, 240, 720],
        seedX: 360,
        seedY: 400,
        style: { kind: 'solid', color: '#B91C1C' },
      },
      {
        id: 'shoeL',
        contour: [280, 920, 340, 920, 340, 1000, 280, 1000],
        seedX: 310,
        seedY: 960,
        style: { kind: 'solid', color: '#111111' },
      },
    ]
    expect(detectFootwearInk([], fills)).toBe(true)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /replace the photo shoes/i.test(h))).toBe(true)
    expect(hints.some((h) => /bare feet/i.test(h))).toBe(false)
  })

  it('promotes pale bridal fills and skips outline ink as solid fill (#182)', () => {
    const fills: FillOp[] = [
      {
        id: 'outline-noise',
        contour: [10, 10, 30, 10, 30, 30, 10, 30],
        seedX: 20,
        seedY: 20,
        style: { kind: 'solid', color: '#111111' },
      },
      {
        id: 'gown',
        // Deep V: shoulders high at y=80, center contour dips to y=260.
        contour: [200, 80, 360, 80, 400, 200, 380, 900, 180, 900, 160, 200, 280, 260],
        seedX: 300,
        seedY: 500,
        style: { kind: 'gradient', colors: ['#F8F4F0', '#D4AF9B'] },
      },
      {
        id: 'leftSleeve',
        contour: [40, 120, 160, 120, 160, 320, 40, 320],
        seedX: 100,
        seedY: 200,
        style: { kind: 'solid', color: '#F8F4F0' },
      },
      {
        id: 'rightSleeve',
        contour: [600, 120, 720, 120, 720, 320, 600, 320],
        seedX: 660,
        seedY: 200,
        style: { kind: 'solid', color: '#F8F4F0' },
      },
    ]
    expect(detectOpenNecklineFromFills(fills)).toBe(true)
    expect(detectBilateralSleevesFromFills(fills)).toBe(true)
    const hints = buildTryOnDesignHints({
      strokes: [stroke({ points: [100, 40, 0.5, 140, 60, 0.5], color: '#111111' })],
      fills,
    })
    expect(hints.some((h) => /plunging|cleavage|open/i.test(h))).toBe(true)
    expect(hints.some((h) => /both.*sleeve/i.test(h))).toBe(true)
    expect(hints.some((h) => /pale|cream|ivory/i.test(h))).toBe(true)
    expect(hints.some((h) => h.includes('solid fill color #111111'))).toBe(false)
    const colorHint = hints.find((h) => h.startsWith('exact designer colors:'))
    expect(colorHint).toBeTruthy()
    expect(colorHint).not.toMatch(/#111111/)
  })

  it('keeps trouser geometry hints inside the 8-hint budget (#172)', () => {
    const fills: FillOp[] = [
      {
        id: 'bodice',
        contour: [300, 80, 460, 80, 460, 420, 300, 420],
        seedX: 380,
        seedY: 240,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'leftLeg',
        contour: [300, 500, 360, 500, 360, 900, 300, 900],
        seedX: 330,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'rightLeg',
        contour: [400, 500, 460, 500, 460, 900, 400, 900],
        seedX: 430,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      // Extra fills that would previously crowd out geometry hints.
      ...Array.from({ length: 6 }, (_, i) => ({
        id: `extra-${i}`,
        contour: [10 + i * 20, 20, 40 + i * 20, 20, 40 + i * 20, 50, 10 + i * 20, 50],
        seedX: 20 + i * 20,
        seedY: 30,
        style: { kind: 'solid' as const, color: `#${(0x111111 * (i + 1)).toString(16).padStart(6, '0')}` },
      })),
    ]
    const strokes: Stroke[] = [
      stroke({ id: 'hat', points: [100, 40, 0.5, 140, 60, 0.5], color: '#222222' }),
      stroke({ id: 's2', points: [200, 50, 0.5, 240, 70, 0.5], color: '#ABCDEF' }),
    ]
    const hints = buildTryOnDesignHints({ strokes, fills })
    expect(hints.length).toBeLessThanOrEqual(8)
    expect(hints.some((h) => /jumpsuit/i.test(h))).toBe(true)
    expect(hints.some((h) => /separate/i.test(h))).toBe(true)
    expect(hints.some((h) => /skirt panel/i.test(h))).toBe(true)
  })

  it('sanitizes see-through fabric wording', () => {
    expect(sanitizeFabricHintText('white White see throgh stockings fabric')).toMatch(/fine-knit/i)
    expect(sanitizeFabricHintText('white White see throgh stockings fabric')).not.toMatch(/see thr/i)
  })

  it('prioritizes stockings and gloves and avoids false one-piece for crop+briefs', () => {
    clearFabricPromptCache()
    rememberFabricPromptShort('stock-1', 'white White see throgh stockings fabric')
    rememberFabricPromptShort('glove-1', 'white gloves fabric')
    const fills: FillOp[] = [
      {
        id: 'top',
        contour: [300, 120, 500, 120, 500, 380, 300, 380],
        seedX: 400,
        seedY: 250,
        style: { kind: 'solid', color: '#F5F0E6' },
      },
      {
        id: 'brief',
        contour: [320, 420, 480, 420, 480, 560, 320, 560],
        seedX: 400,
        seedY: 490,
        style: { kind: 'solid', color: '#F5F0E6' },
      },
      {
        id: 'hose',
        contour: [320, 560, 480, 560, 480, 980, 320, 980],
        seedX: 400,
        seedY: 770,
        style: { kind: 'uploaded-fabric', assetId: 'stock-1', scale: 1 },
      },
      {
        id: 'gloveL',
        contour: [40, 360, 120, 360, 120, 480, 40, 480],
        seedX: 80,
        seedY: 420,
        style: { kind: 'uploaded-fabric', assetId: 'glove-1', scale: 1 },
      },
    ]
    expect(detectSeparateTopBottom(fills)).toBe(true)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /separate top and bottom/i.test(h))).toBe(true)
    expect(hints.some((h) => /stockings\/hosiery/i.test(h))).toBe(true)
    expect(hints.some((h) => /gloves/i.test(h))).toBe(true)
    expect(hints.some((h) => /fine-knit/i.test(h))).toBe(true)
    expect(hints.some((h) => /see thr/i.test(h))).toBe(false)
    expect(hints.some((h) => /continuous one-piece/i.test(h))).toBe(false)
  })
})
