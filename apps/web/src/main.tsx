import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Analytics } from '@vercel/analytics/react'
import { SpeedInsights } from '@vercel/speed-insights/react'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import { AuthProvider } from './lib/auth'
import { RouterProvider } from './lib/router'
import { sanitizeTelemetryEvent } from './lib/telemetry'
import './index.css'

registerSW({ immediate: true })

createRoot(document.getElementById('root')!).render(
  <>
    <StrictMode>
      <AuthProvider>
        <RouterProvider>
          <App />
        </RouterProvider>
      </AuthProvider>
    </StrictMode>
    <Analytics beforeSend={sanitizeTelemetryEvent} />
    <SpeedInsights beforeSend={sanitizeTelemetryEvent} />
  </>
)
