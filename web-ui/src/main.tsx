import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import './styles/global.css'

// Force promptless SW updates so Samsung Internet / returning phones pick up new
// hashed assets without requiring a manual "clear data" every release.
registerSW({
  immediate: true,
  onRegisteredSW(_url, registration) {
    if (!registration) return
    // Recheck for a new worker while the tab is open.
    window.setInterval(() => {
      void registration.update()
    }, 60_000)
  },
})

// Keep the static HTML version bar until React paints, then remove it so the
// GlobalHeader "App …" pill remains the durable signal.
window.addEventListener('DOMContentLoaded', () => {
  window.setTimeout(() => {
    document.getElementById('fr-static-app-version')?.remove()
  }, 4000)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
