/**
 * Real-browser persistence: draw → undo → autosave with delayed/interleaved PUTs.
 * Asserts single-session false conflicts stay closed; genuine multi-tab still opens.
 * No paid AI. Magic never clicked.
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(
  process.env.PLAYWRIGHT_CORE || '/tmp/webv1-qa/node_modules/playwright-core',
)
import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = process.env.OUT_DIR || '/opt/cursor/artifacts/screenshots'
const REPORT = process.env.REPORT_PATH || '/opt/cursor/artifacts/undo-autosave-playwright-report.json'
const PORT = Number(process.env.PORT || 5197)
const BASE = `http://127.0.0.1:${PORT}`

fs.mkdirSync(OUT, { recursive: true })

const result = {
  undoSaveFront: 'FAIL',
  undoSaveBack: 'FAIL',
  multiTabConflict: 'FAIL',
  clearBackIntentSeen: false,
  blockers: [],
  shots: [],
  putLog: [],
}

function emptyDoc(rev = 1) {
  const now = new Date().toISOString()
  return {
    schema: 'fashionrise.studio.draft.v2',
    clientRevision: rev,
    updatedAt: now,
    model: 'female-straight',
    customReferenceUrl: null,
    customReferenceKey: null,
    activeSide: 'front',
    front: { strokes: [], fills: [] },
    back: { strokes: [], fills: [] },
    strokes: [],
    fills: [],
  }
}

function designRow(id, doc, meta = {}) {
  return {
    id,
    user_id: 'u-undo-pw',
    title: 'Studio working draft',
    description: null,
    garment_category: 'studio',
    design_data: doc,
    metadata: {
      draftKind: 'studio_working_draft',
      schema: doc.schema,
      clientRevision: doc.clientRevision,
      ...meta,
    },
    visibility: 'private',
    status: 'draft',
    created_at: '2026-10-26T00:00:00.000Z',
    updated_at: doc.updatedAt || '2026-10-26T00:00:00.000Z',
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function waitForServer(url, timeoutMs = 60000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.ok || res.status === 200) return
    } catch {
      /* retry */
    }
    await sleep(250)
  }
  throw new Error(`server not ready: ${url}`)
}

async function shot(page, name) {
  const p = path.join(OUT, `undo-autosave-${name}.png`)
  await page.screenshot({ path: p, fullPage: false })
  result.shots.push(p)
}

async function designToClient(page, x, y) {
  const stage = page.locator('.konvajs-content').first()
  await stage.waitFor({ state: 'visible', timeout: 20000 })
  const box = await stage.boundingBox()
  if (!box) throw new Error('no stage box')
  return {
    cx: box.x + (x / 768) * box.width,
    cy: box.y + (y / 1024) * box.height,
  }
}

async function drawStroke(page, x0, y0, x1, y1) {
  await page.getByRole('button', { name: /^Pencil$/i }).first().click()
  const a = await designToClient(page, x0, y0)
  const b = await designToClient(page, x1, y1)
  await page.mouse.move(a.cx, a.cy)
  await page.mouse.down()
  await page.mouse.move(b.cx, b.cy, { steps: 12 })
  await page.mouse.up()
  await sleep(200)
}

function startPreview() {
  const env = {
    ...process.env,
    VITE_API_BASE_URL: '/api/v1',
    VITE_REGISTRATION_UI_ENABLED: 'true',
    VITE_MAGIC_UI_ENABLED: 'true',
    VITE_STUDIO_FRONT_BACK_ENABLED: 'true',
    VITE_STUDIO_DUAL_MAGIC_ENABLED: 'true',
  }
  // Prefer already-built dist via vite preview.
  const child = spawn(
    'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'],
    { cwd: ROOT, env, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  let log = ''
  child.stdout.on('data', (d) => {
    log += d.toString()
  })
  child.stderr.on('data', (d) => {
    log += d.toString()
  })
  return { child, getLog: () => log }
}

async function main() {
  const distOk = fs.existsSync(path.join(ROOT, 'dist', 'index.html'))
  if (!distOk) {
    result.blockers.push('dist/ missing — run production build first')
    fs.writeFileSync(REPORT, JSON.stringify(result, null, 2))
    process.exit(2)
  }

  const preview = startPreview()
  try {
    await waitForServer(BASE)

    const server = {
      designId: 'd-undo-pw',
      doc: emptyDoc(1),
      holdPuts: 0,
      releaseHold: null,
      holdPromise: null,
      /** Number of next PUTs that must return a foreign-content 409. */
      forceForeignRemaining: 0,
      foreign409Count: 0,
      putBodies: [],
    }

    const browser = await chromium.launch({
      headless: true,
      executablePath: '/usr/local/bin/google-chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()

    await page.route('**/api/v1/**', async (route) => {
      const req = route.request()
      const url = new URL(req.url())
      const pathname = url.pathname.replace(/^\/api\/v1/, '') || url.pathname
      const method = req.method()

      if (pathname === '/auth/me' && method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'u-undo-pw',
            email: 'undo-pw@fashionrise.local',
            username: 'undopw',
            display_name: 'Undo PW',
            role: 'user',
          }),
        })
        return
      }

      if (pathname === '/designs/my' && method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([designRow(server.designId, server.doc)]),
        })
        return
      }

      if (pathname === `/designs/${server.designId}` && method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(designRow(server.designId, server.doc)),
        })
        return
      }

      if (pathname === `/designs/${server.designId}` && method === 'PUT') {
        const body = req.postDataJSON()
        server.putBodies.push(body)
        result.putLog.push({
          expected: body.expected_revision,
          clearBackIntent: Boolean(body.metadata?.clearBackIntent),
          frontStrokes: body.design_data?.front?.strokes?.length ?? body.design_data?.strokes?.length ?? 0,
          backStrokes: body.design_data?.back?.strokes?.length ?? 0,
          activeSide: body.design_data?.activeSide,
        })

        if (server.holdPuts > 0 && server.holdPromise) {
          server.holdPuts -= 1
          await server.holdPromise
        }

        const expectedRevision = body.expected_revision

        if (server.forceForeignRemaining > 0) {
          server.forceForeignRemaining -= 1
          server.foreign409Count += 1
          const foreignStroke = {
            id: 'other-tab',
            tool: 'draw',
            points: [1, 2, 0.5, 3, 4, 0.5],
            color: '#111111',
            size: 2,
            opacity: 1,
          }
          const foreign = {
            ...emptyDoc(server.doc.clientRevision + 5),
            model: 'male-straight',
            strokes: [foreignStroke],
            front: { strokes: [foreignStroke], fills: [] },
            back: { strokes: [], fills: [] },
          }
          await route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              detail: {
                code: 'conflict',
                message: 'Draft was updated elsewhere.',
                payload: {
                  expected_revision: expectedRevision ?? server.doc.clientRevision,
                  current_revision: foreign.clientRevision,
                  design: designRow(server.designId, foreign),
                },
              },
            }),
          })
          return
        }

        if (expectedRevision != null && expectedRevision !== server.doc.clientRevision) {
          await route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              detail: {
                code: 'conflict',
                message: 'Draft was updated elsewhere.',
                payload: {
                  expected_revision: expectedRevision,
                  current_revision: server.doc.clientRevision,
                  design: designRow(server.designId, server.doc),
                },
              },
            }),
          })
          return
        }

        const next = {
          ...body.design_data,
          clientRevision: (server.doc.clientRevision || 1) + 1,
          updatedAt: new Date().toISOString(),
        }
        // Strip session-only intent from stored cloud doc (mirrors documentForCloud).
        delete next.clearBackIntent
        server.doc = next
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            designRow(server.designId, server.doc, {
              clearBackIntent: Boolean(body.metadata?.clearBackIntent),
            }),
          ),
        })
        return
      }

      if (pathname === '/designs' && method === 'POST') {
        const body = req.postDataJSON()
        server.doc = {
          ...body.design_data,
          clientRevision: 1,
          updatedAt: new Date().toISOString(),
        }
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(designRow(server.designId, server.doc)),
        })
        return
      }

      // Default: empty OK for unrelated probes.
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not mocked"}' })
    })

    await context.addInitScript(() => {
      localStorage.setItem('fr.access_token', 'pw-access')
      localStorage.setItem('fr.refresh_token', 'pw-refresh')
    })

    await page.goto(`${BASE}/studio`, { waitUntil: 'networkidle', timeout: 60000 })
    await page.getByRole('button', { name: /^Pencil$/i }).first().waitFor({ state: 'visible', timeout: 20000 })
    await sleep(500)

    // --- Front: delayed stroke save interleaved with undo ---
    server.holdPromise = new Promise((resolve) => {
      server.releaseHold = resolve
    })
    server.holdPuts = 1

    await drawStroke(page, 300, 280, 420, 340)
    // Wait until the gated PUT is observed (autosave ~1.6s).
    const startHold = Date.now()
    while (result.putLog.length < 1 && Date.now() - startHold < 8000) {
      await sleep(100)
    }
    await page.getByRole('button', { name: /^Undo$/i }).first().click()
    await sleep(300)
    // Queue undo autosave behind the held stroke PUT.
    server.releaseHold?.()
    await sleep(2500)

    const conflictVisible = await page.getByRole('button', { name: 'Keep this device' }).isVisible().catch(() => false)
    const saveFailed = await page.getByText(/Save failed|Draft recovery|updated elsewhere/i).isVisible().catch(() => false)
    await shot(page, 'front-after-undo-save')
    if (!conflictVisible && !saveFailed) {
      result.undoSaveFront = 'PASS'
    } else {
      result.blockers.push(`front undo→save surfaced conflict/error (conflict=${conflictVisible} saveFailed=${saveFailed})`)
    }

    // --- Back: stroke → save → undo empty must stamp clearBackIntent, no conflict ---
    const flip = page.getByTestId('flip-paper-button')
    if (await flip.isVisible().catch(() => false)) {
      await flip.click()
      await sleep(600)
      await drawStroke(page, 310, 300, 430, 360)
      await sleep(2200) // allow back stroke autosave
      const putsBeforeUndo = result.putLog.length
      await page.getByRole('button', { name: /^Undo$/i }).first().click()
      await sleep(2200)
      const backClears = result.putLog.slice(putsBeforeUndo).filter((p) => p.clearBackIntent && p.backStrokes === 0)
      result.clearBackIntentSeen = backClears.length > 0
      const conflictBack = await page.getByRole('button', { name: 'Keep this device' }).isVisible().catch(() => false)
      await shot(page, 'back-after-undo-save')
      if (!conflictBack && result.clearBackIntentSeen) {
        result.undoSaveBack = 'PASS'
      } else {
        result.blockers.push(
          `back undo→save conflict=${conflictBack} clearBackIntentSeen=${result.clearBackIntentSeen}`,
        )
      }
      // Return to front for multi-tab check.
      await flip.click()
      await sleep(400)
    } else {
      result.blockers.push('flip control missing — Front/Back flag not live in preview build')
    }

    // --- Genuine multi-tab: foreign content must open conflict ---
    server.forceForeignRemaining = 3
    await drawStroke(page, 280, 400, 400, 460)
    // Wait for autosave + conflict UI (may retry once after same-session recovery paths).
    const multiStart = Date.now()
    let multiOk = false
    while (Date.now() - multiStart < 8000) {
      multiOk = await page.getByRole('button', { name: 'Keep this device' }).isVisible().catch(() => false)
      if (multiOk) break
      await sleep(200)
    }
    await shot(page, 'multi-tab-conflict')
    result.multiTabConflict = multiOk ? 'PASS' : 'FAIL'
    result.foreign409Count = server.foreign409Count
    if (!multiOk) {
      result.blockers.push(
        `expected Keep this device for foreign-tab 409 (foreign409Count=${server.foreign409Count})`,
      )
    }

    await browser.close()
  } catch (err) {
    result.blockers.push(String(err))
  } finally {
    preview.child.kill('SIGTERM')
    fs.writeFileSync(REPORT, JSON.stringify(result, null, 2))
    console.log(JSON.stringify(result, null, 2))
  }

  const failed =
    result.undoSaveFront !== 'PASS' ||
    result.undoSaveBack !== 'PASS' ||
    result.multiTabConflict !== 'PASS'
  process.exit(failed ? 1 : 0)
}

main()
