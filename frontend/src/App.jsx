import { Suspense, lazy } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Footer from './components/Footer'
import Header from './components/Header'
import CatalogPage from './pages/CatalogPage'
import HomePage from './pages/HomePage'
import ImportPage from './pages/ImportPage'
import LoginPage from './pages/LoginPage'
import MarketPage from './pages/MarketPage'
import ProductPage from './pages/ProductPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'
import SellerAnalyticsPage from './pages/SellerAnalyticsPage'
import SellerPage from './pages/SellerPage'
import { useAuth } from './services/auth.jsx'

// Pages for guests only: logged-in users are sent home
function GuestOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/" replace /> : children
}

// Pages for one role only: others are sent home
function RoleOnly({ role, children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user?.role === role ? children : <Navigate to="/" replace />
}

// Any logged-in user; guests go to the login page
function UserOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? children : <Navigate to="/login" replace />
}

// The catalog lived on "/" before phase B2: old links with a search or filters ("/?category=ram&f_type=DDR5") still work
function HomeOrOldCatalog() {
  const { search } = useLocation()
  return search ? <Navigate to={`/catalog${search}`} replace /> : <HomePage />
}

// The components page exists only in development: the public build does not contain it
const UiPage = import.meta.env.DEV ? lazy(() => import('./pages/UiPage')) : null

// Set only for the public server build (deploy.bat)
const PUBLIC_DEMO = import.meta.env.VITE_PUBLIC_DEMO === '1'

function DemoBanner() {
  const { t } = useTranslation()
  return (
    <div className="bg-ink px-4 py-1.5 text-center text-xs text-white/85">
      {t('demo.banner')}
    </div>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      {PUBLIC_DEMO && <DemoBanner />}
      <Header />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6 md:py-8">
        <Routes>
          <Route path="/" element={<HomeOrOldCatalog />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
          <Route path="/market" element={<MarketPage />} />
          <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
          <Route path="/seller" element={<RoleOnly role="seller"><SellerPage /></RoleOnly>} />
          <Route path="/seller/analytics" element={<RoleOnly role="seller"><SellerAnalyticsPage /></RoleOnly>} />
          <Route path="/seller/imports/:id" element={<RoleOnly role="seller"><ImportPage /></RoleOnly>} />
          <Route path="/profile" element={<UserOnly><ProfilePage /></UserOnly>} />
          {UiPage && <Route path="/ui" element={<Suspense fallback={null}><UiPage /></Suspense>} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
