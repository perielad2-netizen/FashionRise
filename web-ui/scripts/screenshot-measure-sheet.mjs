/**
 * Headless Chrome screenshots of the real MeasurementsSheet at Android widths.
 * Serves a tiny harness that mounts the production component with fixture props.
 */
import { createServer } from 'node:http'
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const outDir = '/opt/cursor/artifacts/techpack-crit-fix'
mkdirSync(outDir, { recursive: true })

const entry = join(root, 'scripts/measure-sheet-harness.tsx')
writeFileSync(
  entry,
  `
import { createRoot } from 'react-dom/client'
import { useState } from 'react'
import { MeasurementsSheet } from '../src/shell/components/techpack/MeasurementsSheet'
import type { TechpackPiece, TechpackSpecV2 } from '../src/services/techpacksApi'

const piece: TechpackPiece = {
  id: 'piece-1',
  category: 'dress',
  role: 'ONE_PIECE',
  label: 'Pink dress',
  finished_measurements: {
    chest_bust: { value: null, unit: 'cm', source: 'empty' },
    garment_length: { value: 110, unit: 'cm', source: 'estimate' },
    sleeve_length: { value: null, unit: 'cm', source: 'empty' },
  },
}

const initial: TechpackSpecV2 = {
  schema_version: '2.0',
  units: 'cm',
  body: {
    height: { value: null, unit: 'cm', source: 'empty' },
    bust: { value: null, unit: 'cm', source: 'empty' },
    waist: { value: null, unit: 'cm', source: 'empty' },
    hip: { value: null, unit: 'cm', source: 'empty' },
  },
  preferences: { fit_preference: 'regular', notes: '' },
  outfit: { piece_count: 1, pieces: [piece] },
}

function App() {
  const [spec, setSpec] = useState(initial)
  const [pieces, setPieces] = useState([piece])
  return (
    <div style={{ minHeight: '100vh', background: '#0b0e14', color: '#fff', fontFamily: 'system-ui' }}>
      <MeasurementsSheet
        open
        spec={spec}
        pieces={pieces}
        onChangeSpec={(updater) => setSpec((prev) => updater(prev))}
        onUpdatePiece={(id, updater) => {
          setPieces((prev) => prev.map((p) => (p.id === id ? updater(p) : p)))
          setSpec((prev) => ({
            ...prev,
            outfit: {
              ...(prev.outfit ?? { piece_count: 0, pieces: [] }),
              pieces: (prev.outfit?.pieces ?? []).map((p) => (p.id === id ? updater(p) : p)),
            },
          }))
        }}
        onSaveAndDone={() => undefined}
        onDiscardAndClose={() => undefined}
      />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
`,
)

await build({
  entryPoints: [entry],
  bundle: true,
  outfile: join(outDir, 'harness.js'),
  format: 'esm',
  jsx: 'automatic',
  loader: { '.css': 'css' },
  define: { 'process.env.NODE_ENV': '"development"' },
  alias: { '@': join(root, 'src') },
})

// esbuild CSS sidecar
const cssPath = join(outDir, 'harness.css')
if (!existsSync(cssPath)) writeFileSync(cssPath, '')

writeFileSync(
  join(outDir, 'index.html'),
  `<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><link rel="stylesheet" href="./harness.css"/></head><body><div id="root"></div><script type="module" src="./harness.js"></script></body></html>`,
)

const server = createServer((req, res) => {
  const url = req.url === '/' ? '/index.html' : req.url
  const path = join(outDir, url.replace(/^\//, ''))
  try {
    const data = readFileSync(path)
    res.writeHead(200, {
      'Content-Type': path.endsWith('.js')
        ? 'text/javascript'
        : path.endsWith('.css')
          ? 'text/css'
          : 'text/html',
    })
    res.end(data)
  } catch {
    res.writeHead(404)
    res.end('missing')
  }
})
await new Promise((r) => server.listen(4177, '127.0.0.1', r))

const widths = [360, 390, 430]
for (const w of widths) {
  const out = join(outDir, `measure-sheet-${w}.png`)
  await new Promise((resolve, reject) => {
    const chrome = spawn(
      'google-chrome',
      [
        '--headless=new',
        '--disable-gpu',
        '--no-sandbox',
        `--window-size=${w},800`,
        `--screenshot=${out}`,
        `http://127.0.0.1:4177/`,
      ],
      { stdio: 'inherit' },
    )
    chrome.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`chrome ${code}`))))
  })
  console.log('shot', out)
}

server.close()
console.log('SCREENSHOTS_OK')
