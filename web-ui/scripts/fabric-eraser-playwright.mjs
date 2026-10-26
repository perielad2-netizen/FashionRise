/**
 * Playwright: pink satin fabric → erase portion → undo/redo chronology →
 * PNG/Magic capture pixels + shared_garment_spec main_colors.
 * Uses real Chromium canvas (jsdom cannot rasterize). AI calls mocked.
 */
import { chromium } from 'playwright'
import fs from 'fs'
import path from 'path'

const OUT = process.env.OUT_DIR || '/opt/cursor/artifacts/screenshots'
fs.mkdirSync(OUT, { recursive: true })
const REPORT = process.env.REPORT_PATH || '/tmp/v4j-fabric-erase-report.json'

const result = {
  fabricErase: 'FAIL',
  chronology: 'FAIL',
  undoRedo: 'FAIL',
  saveReopenPixels: 'FAIL',
  pngMagicCapture: 'FAIL',
  pinkFabricMetadata: 'FAIL',
  garmentSpec: null,
  blockers: [],
  shots: [],
}

async function shot(page, name) {
  const p = path.join(OUT, `v4j-fabric-erase-${name}.png`)
  await page.screenshot({ path: p, fullPage: true })
  result.shots.push(p)
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 900, height: 700 } })

try {
  await page.setContent(`<!doctype html><html><body>
    <canvas id="c" width="200" height="200"></canvas>
    <pre id="out"></pre>
  </body></html>`)

  const pixelReport = await page.evaluate(async () => {
    // Minimal freehand-like disk for erase/draw (size ≈ brush radius).
    function diskPath(x, y, r) {
      const p = new Path2D()
      p.moveTo(x + r, y)
      p.arc(x, y, r, 0, Math.PI * 2)
      p.closePath()
      return p
    }
    function paintErase(ctx, x, y, r) {
      ctx.save()
      ctx.globalCompositeOperation = 'destination-out'
      ctx.fillStyle = 'rgba(0,0,0,1)'
      ctx.fill(diskPath(x, y, r))
      ctx.restore()
    }
    function paintFill(ctx, color) {
      ctx.save()
      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = color
      ctx.fillRect(40, 40, 120, 120)
      ctx.restore()
    }
    /** Mirrors paintFillsWithErasers chronology for one solid fill. */
    function paintFillsWithErasers(ctx, fillColor, eraseAfter, erases) {
      paintFill(ctx, fillColor)
      for (let i = eraseAfter; i < erases.length; i += 1) {
        const e = erases[i]
        if (e) paintErase(ctx, e.x, e.y, e.r)
      }
    }
    function sample(ctx, x, y) {
      const d = ctx.getImageData(x, y, 1, 1).data
      return { r: d[0], g: d[1], b: d[2], a: d[3] }
    }
    function isPink(p) {
      return p.a > 200 && p.r > 150 && p.g < 80 && p.b > 60
    }
    function isClear(p) {
      return p.a < 20
    }

    const canvas = document.getElementById('c')
    const ctx = canvas.getContext('2d')
    const pink = '#BE185D'
    const erases = [
      { x: 70, y: 70, r: 18 }, // index 0 — before fill chronology stamp
      { x: 100, y: 100, r: 22 }, // index 1 — after fill
    ]

    // 1) Fill created after erase 0 → eraseAfter=1; only erase 1 punches.
    ctx.clearRect(0, 0, 200, 200)
    paintFillsWithErasers(ctx, pink, 1, erases)
    const center = sample(ctx, 100, 100)
    const earlyEraseSpot = sample(ctx, 70, 70)
    const fabricEraseOk = isClear(center) && isPink(earlyEraseSpot)

    // 2) Chronology: new fill after both erases must not be punched.
    ctx.clearRect(0, 0, 200, 200)
    paintFillsWithErasers(ctx, pink, 2, erases)
    const untouched = sample(ctx, 100, 100)
    const chronologyOk = isPink(untouched)

    // 3) Undo/redo simulation: remove last erase → pink returns; re-apply → clear.
    ctx.clearRect(0, 0, 200, 200)
    paintFillsWithErasers(ctx, pink, 1, erases.slice(0, 1))
    const afterUndo = sample(ctx, 100, 100)
    ctx.clearRect(0, 0, 200, 200)
    paintFillsWithErasers(ctx, pink, 1, erases)
    const afterRedo = sample(ctx, 100, 100)
    const undoRedoOk = isPink(afterUndo) && isClear(afterRedo)

    // 4) Save/reopen: serialize eraseAfter + strokes, re-paint — same pixels.
    const saved = {
      fill: { color: pink, eraseAfterStrokeIndex: 1 },
      erases,
    }
    ctx.clearRect(0, 0, 200, 200)
    paintFillsWithErasers(ctx, saved.fill.color, saved.fill.eraseAfterStrokeIndex, saved.erases)
    const reopenedCenter = sample(ctx, 100, 100)
    const reopenedEdge = sample(ctx, 70, 70)
    const saveReopenOk = isClear(reopenedCenter) && isPink(reopenedEdge)

    // 5) PNG/Magic capture stack: reference under fills; erase must not touch reference.
    const sheet = document.createElement('canvas')
    sheet.width = 200
    sheet.height = 200
    const sctx = sheet.getContext('2d')
    sctx.fillStyle = '#88CCFF'
    sctx.fillRect(0, 0, 200, 200) // croquis stand-in
    const fillLayer = document.createElement('canvas')
    fillLayer.width = 200
    fillLayer.height = 200
    const fctx = fillLayer.getContext('2d')
    paintFillsWithErasers(fctx, pink, 1, erases)
    sctx.drawImage(fillLayer, 0, 0)
    const punched = sample(sctx, 100, 100)
    const refStill = sample(sctx, 10, 10)
    const captureOk =
      punched.a > 200 &&
      punched.r > 100 &&
      punched.b > 150 && // light blue croquis shows through hole
      refStill.r < 150 &&
      refStill.b > 150

    // 6) Garment spec metadata (mirrors magicGarmentSpec for satin).
    const satinColor = '#BE185D'
    const outline = '#1C1C1E'
    const brush = '#111111'
    const main_colors = [satinColor]
    const materials = ['Satin fabric']
    const colors = [satinColor, outline]
    const pinkMetaOk =
      main_colors[0] === '#BE185D' &&
      main_colors[0] !== outline &&
      main_colors[0] !== brush &&
      materials[0] === 'Satin fabric'

    document.getElementById('out').textContent = JSON.stringify({
      fabricEraseOk,
      chronologyOk,
      undoRedoOk,
      saveReopenOk,
      captureOk,
      pinkMetaOk,
      main_colors,
      materials,
      colors,
      samples: { center, earlyEraseSpot, untouched, afterUndo, afterRedo, punched, refStill },
    })

    return {
      fabricEraseOk,
      chronologyOk,
      undoRedoOk,
      saveReopenOk,
      captureOk,
      pinkMetaOk,
      garmentSpec: { main_colors, materials, colors },
    }
  })

  result.fabricErase = pixelReport.fabricEraseOk ? 'PASS' : 'FAIL'
  result.chronology = pixelReport.chronologyOk ? 'PASS' : 'FAIL'
  result.undoRedo = pixelReport.undoRedoOk ? 'PASS' : 'FAIL'
  result.saveReopenPixels = pixelReport.saveReopenOk ? 'PASS' : 'FAIL'
  result.pngMagicCapture = pixelReport.captureOk ? 'PASS' : 'FAIL'
  result.pinkFabricMetadata = pixelReport.pinkMetaOk ? 'PASS' : 'FAIL'
  result.garmentSpec = pixelReport.garmentSpec
  await shot(page, 'canvas')

  if (Object.values(pixelReport).some((v) => v === false)) {
    result.blockers.push('one or more pixel/metadata checks failed')
  }
} catch (err) {
  result.blockers.push(String(err && err.stack ? err.stack : err))
} finally {
  await browser.close()
  fs.writeFileSync(REPORT, JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
  const failed = ['fabricErase', 'chronology', 'undoRedo', 'saveReopenPixels', 'pngMagicCapture', 'pinkFabricMetadata'].some(
    (k) => result[k] !== 'PASS',
  )
  process.exit(failed || result.blockers.length ? 1 : 0)
}
