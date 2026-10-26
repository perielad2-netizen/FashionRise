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

// Keep the sticky HTML "FashionRise App …" bar for the whole session.
// Phones were missing the build id when we removed it after paint; the bar is
// the unmistakable proof the browser loaded this release (not a cached shell).

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
