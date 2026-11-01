import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './i18n'
import App from './App.jsx'
import { ToastProvider } from './components/overlays'
import { AuthProvider } from './services/auth.jsx'
import { CityProvider } from './services/city.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CityProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </CityProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
