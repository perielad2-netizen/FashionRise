import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import { bootstrapNativeShell } from './services/native/bootstrap'
import { isNativeBuild, isNativeShell } from './services/native/platform'
import './styles/global.css'

// PWA service worker is for the browser install path only.
// Capacitor store shells must not register a SW (conflicts with the native WebView).
if (!isNativeBuild() && !isNativeShell()) {
  registerSW({
    immediate: true,
    onRegisteredSW(_url, registration) {
      if (!registration) return
      window.setInterval(() => {
        void registration.update()
      }, 60_000)
    },
  })
}

void bootstrapNativeShell()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
