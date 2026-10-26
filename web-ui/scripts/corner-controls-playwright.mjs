/**
 * Verify Full Screen + Flip stay inside the paper frame across viewports.
 */
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require(
  process.env.PLAYWRIGHT_CORE || '/tmp/webv1-qa/node_modules/playwright-core',
)

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = process.env.OUT_DIR || '/opt/cursor/artifacts/screenshots'
const REPORT = process.env.REPORT_PATH || '/opt/cursor/artifacts/corner-controls-report.json'
const PORT = Number(process.env.PORT || 5198)
const BASE = `http://127.0.0.1:${PORT}`

fs.mkdirSync(OUT, { recursive: true })

const VIEWPORTS = [
  { name: 'phone-375x667', w: 375, h: 667 },
  { name: 'phone-390x844', w: 390, h: 844 },
  { name: 'phone-landscape-844x390', w: 844, h: 390 },
  { name: 'tablet-768x1024', w: 768, h: 1024 },
  { name: 'desktop-1440x900', w: 1440, h: 900 },
]

const result = {
  viewports: {},
  flipWorks: 'FAIL',
  fullscreenEnter: 'FAIL',
  immersiveNoDuplicate: 'FAIL',
  fullscreenExitRestores: 'FAIL',
  blockers: [],
  shots: [],
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

function startPreview() {
  const env = {
    ...process.env,
    VITE_API_BASE_URL: '/api/v1',
    VITE_REGISTRATION_UI_ENABLED: 'true',
    VITE_MAGIC_UI_ENABLED: 'true',
    VITE_STUDIO_FRONT_BACK_ENABLED: 'true',
    VITE_STUDIO_DUAL_MAGIC_ENABLED: 'true',
  }
  const child = spawn(
    'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'],
    { cwd: ROOT, env, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  return child
}

function emptyDoc() {
  const now = new Date().toISOString()
  return {
    schema: 'fashionrise.studio.draft.v2',
    clientRevision: 1,
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

function inside(outer, inner, pad = 0.5) {
  return (
    inner.x >= outer.x - pad &&
    inner.y >= outer.y - pad &&
    inner.x + inner.width <= outer.x + outer.width + pad &&
    inner.y + inner.height <= outer.y + outer.height + pad
  )
}

function overlap(a, b) {
  return !(
    a.x + a.width <= b.x ||
    b.x + b.width <= a.x ||
    a.y + a.height <= b.y ||
    b.y + b.height <= a.y
  )
}

async function main() {
  if (!fs.existsSync(path.join(ROOT, 'dist', 'index.html'))) {
    result.blockers.push('dist/ missing')
    fs.writeFileSync(REPORT, JSON.stringify(result, null, 2))
    process.exit(2)
  }

  const child = startPreview()
  try {
    await waitForServer(BASE)
    const browser = await chromium.launch({
      headless: true,
      executablePath: '/usr/local/bin/google-chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    })

    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({ viewport: { width: vp.w, height: vp.h } })
      const page = await context.newPage()
      await page.route('**/api/v1/**', async (route) => {
        const url = new URL(route.request().url())
        const pathname = url.pathname.replace(/^\/api\/v1/, '')
        const method = route.request().method()
        if (pathname === '/auth/me' && method === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 'u-corner',
              email: 'corner@fashionrise.local',
              username: 'corner',
              display_name: 'Corner',
              role: 'user',
            }),
          })
          return
        }
        if (pathname === '/designs/my' && method === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify([
              {
                id: 'd-corner',
                user_id: 'u-corner',
                title: 'Studio working draft',
                description: null,
                garment_category: 'studio',
                design_data: emptyDoc(),
                metadata: { draftKind: 'studio_working_draft', schema: 'fashionrise.studio.draft.v2' },
                visibility: 'private',
                status: 'draft',
                created_at: '2026-10-26T00:00:00.000Z',
                updated_at: '2026-10-26T00:00:00.000Z',
              },
            ]),
          })
          return
        }
        if (pathname.startsWith('/designs/') && method === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 'd-corner',
              user_id: 'u-corner',
              title: 'Studio working draft',
              description: null,
              garment_category: 'studio',
              design_data: emptyDoc(),
              metadata: { draftKind: 'studio_working_draft', schema: 'fashionrise.studio.draft.v2' },
              visibility: 'private',
              status: 'draft',
              created_at: '2026-10-26T00:00:00.000Z',
              updated_at: '2026-10-26T00:00:00.000Z',
            }),
          })
          return
        }
        if ((pathname === '/designs' && method === 'POST') || (pathname.startsWith('/designs/') && method === 'PUT')) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 'd-corner',
              user_id: 'u-corner',
              title: 'Studio working draft',
              garment_category: 'studio',
              design_data: emptyDoc(),
              metadata: { draftKind: 'studio_working_draft' },
              visibility: 'private',
              status: 'draft',
              created_at: '2026-10-26T00:00:00.000Z',
              updated_at: new Date().toISOString(),
            }),
          })
          return
        }
        await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not mocked"}' })
      })
      await context.addInitScript(() => {
        localStorage.setItem('fr.access_token', 'pw')
        localStorage.setItem('fr.refresh_token', 'pw')
      })

      await page.goto(`${BASE}/studio`, { waitUntil: 'networkidle', timeout: 60000 })
      await page.getByTestId('paper-frame').waitFor({ state: 'visible', timeout: 20000 })
      await sleep(400)

      const paper = page.getByTestId('paper-frame')
      const fsBtn = page.getByTestId('paper-fullscreen-button')
      const flip = page.getByTestId('flip-paper-control')
      const paperBox = await paper.boundingBox()
      const fsBox = await fsBtn.boundingBox()
      const flipBox = await flip.boundingBox()
      const shot = path.join(OUT, `corner-controls-${vp.name}.png`)
      await page.screenshot({ path: shot, fullPage: false })
      result.shots.push(shot)

      const entry = {
        paper: paperBox,
        fullscreen: fsBox,
        flip: flipBox,
        fsInside: false,
        flipInside: false,
        noOverlap: false,
        fsMinTouch: false,
        flipMinTouch: false,
        fsIconPreferred: null,
        flipLabelReadable: null,
        status: 'FAIL',
      }
      if (paperBox && fsBox && flipBox) {
        entry.fsInside = inside(paperBox, fsBox)
        entry.flipInside = inside(paperBox, flipBox)
        entry.noOverlap = !overlap(fsBox, flipBox)
        entry.fsMinTouch = fsBox.width >= 43.5 && fsBox.height >= 43.5
        entry.flipMinTouch = flipBox.height >= 43.5
        // Phone-scale paper (≤420px): Full Screen should be icon-only (~44×44).
        if (paperBox.width <= 420) {
          entry.fsIconPreferred = fsBox.width <= 52 && fsBox.height <= 52
        } else {
          entry.fsIconPreferred = true
        }
        // Front/Back state remains readable (FRONT/BACK label present).
        const sideText = (await flip.innerText()).trim()
        entry.flipLabelReadable = /FRONT|BACK/i.test(sideText)
        entry.status =
          entry.fsInside &&
          entry.flipInside &&
          entry.noOverlap &&
          entry.fsMinTouch &&
          entry.flipMinTouch &&
          entry.fsIconPreferred &&
          entry.flipLabelReadable
            ? 'PASS'
            : 'FAIL'
      }
      result.viewports[vp.name] = entry
      if (entry.status !== 'PASS') {
        result.blockers.push(`${vp.name}: ${JSON.stringify(entry)}`)
      }
      await context.close()
    }

    // Interaction: flip + enter fullscreen on desktop
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url())
      const pathname = url.pathname.replace(/^\/api\/v1/, '')
      if (pathname === '/auth/me') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'u-corner',
            email: 'corner@fashionrise.local',
            username: 'corner',
            display_name: 'Corner',
            role: 'user',
          }),
        })
        return
      }
      if (pathname === '/designs/my' || pathname.startsWith('/designs')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            pathname === '/designs/my'
              ? [
                  {
                    id: 'd-corner',
                    user_id: 'u-corner',
                    title: 'Studio working draft',
                    garment_category: 'studio',
                    design_data: emptyDoc(),
                    metadata: { draftKind: 'studio_working_draft', schema: 'fashionrise.studio.draft.v2' },
                    visibility: 'private',
                    status: 'draft',
                    created_at: '2026-10-26T00:00:00.000Z',
                    updated_at: '2026-10-26T00:00:00.000Z',
                  },
                ]
              : {
                  id: 'd-corner',
                  user_id: 'u-corner',
                  title: 'Studio working draft',
                  garment_category: 'studio',
                  design_data: emptyDoc(),
                  metadata: { draftKind: 'studio_working_draft', schema: 'fashionrise.studio.draft.v2' },
                  visibility: 'private',
                  status: 'draft',
                  created_at: '2026-10-26T00:00:00.000Z',
                  updated_at: '2026-10-26T00:00:00.000Z',
                },
          ),
        })
        return
      }
      await route.fulfill({ status: 404, body: '{}' })
    })
    await context.addInitScript(() => {
      localStorage.setItem('fr.access_token', 'pw')
      localStorage.setItem('fr.refresh_token', 'pw')
    })
    await page.goto(`${BASE}/studio`, { waitUntil: 'networkidle', timeout: 60000 })
    await page.getByTestId('flip-paper-button').click()
    await sleep(300)
    const side = await page.getByTestId('flip-paper-control').getAttribute('data-side')
    result.flipWorks = side === 'back' ? 'PASS' : 'FAIL'
    if (result.flipWorks !== 'PASS') result.blockers.push(`flip side=${side}`)

    await page.getByTestId('paper-fullscreen-button').click()
    await sleep(500)
    const immersive = await page.locator('[data-immersive="true"]').count()
    result.fullscreenEnter = immersive > 0 ? 'PASS' : 'FAIL'
    const paperFsWhileImmersive = await page.getByTestId('paper-fullscreen-button').count()
    result.immersiveNoDuplicate = paperFsWhileImmersive === 0 ? 'PASS' : 'FAIL'
    if (result.fullscreenEnter !== 'PASS') result.blockers.push('immersive not entered')
    if (result.immersiveNoDuplicate !== 'PASS') result.blockers.push('duplicate paper fullscreen in immersive')

    await page.screenshot({
      path: path.join(OUT, 'corner-controls-immersive.png'),
      fullPage: false,
    })
    result.shots.push(path.join(OUT, 'corner-controls-immersive.png'))

    // Exit immersive: prefer DOM click on the exit control (avoids picker scrims).
    await page.evaluate(() => {
      const btn = document.querySelector('[data-testid="immersive-exit"]')
      if (btn instanceof HTMLElement) btn.click()
    })
    await sleep(500)
    let restoredFs = await page.getByTestId('paper-fullscreen-button').count()
    let stillImmersive = await page
      .locator('[aria-label="Creator workspace"][data-immersive="true"]')
      .count()
    if (restoredFs !== 1 || stillImmersive !== 0) {
      // Fallback: Escape exits immersive when no modal owns the key.
      await page.keyboard.press('Escape')
      await sleep(400)
      restoredFs = await page.getByTestId('paper-fullscreen-button').count()
      stillImmersive = await page
        .locator('[aria-label="Creator workspace"][data-immersive="true"]')
        .count()
    }
    result.fullscreenExitRestores =
      restoredFs === 1 && stillImmersive === 0 ? 'PASS' : 'FAIL'
    if (result.fullscreenExitRestores !== 'PASS') {
      result.blockers.push(
        `exit restore fs=${restoredFs} immersive=${stillImmersive}`,
      )
    }

    await browser.close()
  } catch (err) {
    result.blockers.push(String(err))
  } finally {
    child.kill('SIGTERM')
    fs.writeFileSync(REPORT, JSON.stringify(result, null, 2))
    console.log(JSON.stringify(result, null, 2))
  }

  const vpFail = Object.values(result.viewports).some((v) => v.status !== 'PASS')
  const failed =
    vpFail ||
    result.flipWorks !== 'PASS' ||
    result.fullscreenEnter !== 'PASS' ||
    result.immersiveNoDuplicate !== 'PASS' ||
    result.fullscreenExitRestores !== 'PASS' ||
    result.blockers.length > 0
  process.exit(failed ? 1 : 0)
}

main()
