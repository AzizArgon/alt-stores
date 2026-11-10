import { Suspense, lazy, useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { isExternal } from './config/sites'
import ChatView, { OpenConversation } from './components/Chat'
import StoreLayout from './layouts/StoreLayout'
import BuildPage from './pages/BuildPage'
import BuildsPage from './pages/BuildsPage'
import CatalogPage from './pages/CatalogPage'
import HomePage from './pages/HomePage'
import ImportPage from './pages/ImportPage'
import LoginPage from './pages/LoginPage'
import MarketPage from './pages/MarketPage'
import ProductPage from './pages/ProductPage'
import StorePage from './pages/StorePage'
import StoresPage from './pages/StoresPage'
import UsedPage from './pages/UsedPage'
import ProfilePage from './pages/ProfilePage'
import ReservationsPage from './pages/ReservationsPage'
import SellerReservationsPage from './pages/SellerReservationsPage'
import RegisterPage from './pages/RegisterPage'
import SellerAnalyticsPage from './pages/SellerAnalyticsPage'
import CabinetOverview from './pages/CabinetOverview'
import GoodsPage from './pages/GoodsPage'
import WarehousePage, { ReportsPage } from './pages/WarehousePage'
import ScanPage from './pages/ScanPage'
import SellerBuildsPage, { SellerBuildEditPage } from './pages/SellerBuildsPage'
import SellerLayout, { AddSection, ImportsSection, NotSellerPage, ProfileSection, SellerAuthLayout } from './pages/SellerPage'
import AdminLayout, { AdminAuthLayout, AdminLog, AdminLoginPage, AdminOverview, AdminUsers, NoAccessPage } from './pages/AdminPage'
import { AdminBarcodes, AdminChannels, AdminFixes, AdminFlags, AdminReports, AdminStoreCard, AdminStores } from './pages/AdminModeration'
import { useAuth } from './services/auth.jsx'
import { adminGate, homeFor, returnTo, sellerGate } from './services/roles'

// Goes to an address of this site, or reloads to another one (the cabinet on its own subdomain later)
function Redirect({ to }) {
  const external = isExternal(to)
  useEffect(() => { if (external) window.location.replace(to) }, [external, to])
  return external ? null : <Navigate to={to} replace />
}

// Pages for guests only: a logged-in user goes to his own interface (a seller to the cabinet)
function GuestOnly({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  return user ? <Redirect to={returnTo(user, location.state?.from)} /> : children
}

// The seller cabinet: a guest goes to the seller login, a buyer sees "this section is for sellers"
function SellerOnly({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  const gate = sellerGate(user)
  if (gate === 'login') return <Navigate to="/seller/login" replace state={{ from: location.pathname + location.search }} />
  if (gate === 'notSeller') return <NotSellerPage />
  return children
}

// The admin panel (phase 13): a guest goes to the admin login, a seller or a buyer sees "no access"
function AdminOnly({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  const gate = adminGate(user)
  if (gate === 'login') return <Navigate to="/admin/login" replace state={{ from: location.pathname + location.search }} />
  if (gate === 'noAccess') return <NoAccessPage />
  return children
}

// Any logged-in user; guests go to the login page
function UserOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? children : <Navigate to="/login" replace />
}

// Buyer's messages: a guest logs in and comes back to the same address ("Write" -> login -> the conversation);
// a seller has his messages in the cabinet
function BuyerOnly({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (user.role === 'seller' || user.role === 'admin') return <Redirect to={homeFor(user)} />
  return children
}

// The catalog lived on "/" before phase B2: old links with a search or filters ("/?category=ram&f_type=DDR5") still work
function HomeOrOldCatalog() {
  const { search } = useLocation()
  return search ? <Navigate to={`/catalog${search}`} replace /> : <HomePage />
}

// The components page exists only in development: the public build does not contain it
const UiPage = import.meta.env.DEV ? lazy(() => import('./pages/UiPage')) : null

// Two interfaces on one site and one database: the storefront and the seller cabinet (/seller).
// Phase 13: the admin (/admin) is the third one on the same Workspace frame.
export default function App() {
  return (
    <Routes>
      <Route element={<StoreLayout />}>
        <Route path="/" element={<HomeOrOldCatalog />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/products/:id" element={<ProductPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/used" element={<UsedPage />} />
        <Route path="/builds" element={<BuildsPage />} />
        <Route path="/builds/:id" element={<BuildPage />} />
        <Route path="/stores" element={<StoresPage />} />
        <Route path="/store/:id" element={<StorePage />} />
        <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
        <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
        <Route path="/messages" element={<BuyerOnly><ChatView base="/messages" side="buyer" /></BuyerOnly>} />
        <Route path="/messages/new" element={<BuyerOnly><OpenConversation /></BuyerOnly>} />
        <Route path="/messages/:id" element={<BuyerOnly><ChatView base="/messages" side="buyer" /></BuyerOnly>} />
        <Route path="/reservations" element={<BuyerOnly><ReservationsPage /></BuyerOnly>} />
        <Route path="/profile" element={<UserOnly><ProfilePage /></UserOnly>} />
        {UiPage && <Route path="/ui" element={<Suspense fallback={null}><UiPage /></Suspense>} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>

      <Route element={<SellerAuthLayout />}>
        <Route path="/seller/login" element={<GuestOnly><LoginPage seller /></GuestOnly>} />
        <Route path="/seller/register" element={<GuestOnly><RegisterPage seller /></GuestOnly>} />
      </Route>
      <Route path="/seller" element={<SellerOnly><SellerLayout /></SellerOnly>}>
        <Route index element={<CabinetOverview />} />
        <Route path="goods" element={<GoodsPage />} />
        <Route path="stock" element={<WarehousePage />} />
        <Route path="scan" element={<ScanPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="builds" element={<SellerBuildsPage />} />
        <Route path="builds/new" element={<SellerBuildEditPage />} />
        <Route path="builds/:id" element={<SellerBuildEditPage />} />
        <Route path="add" element={<AddSection />} />
        <Route path="imports" element={<ImportsSection />} />
        <Route path="imports/:id" element={<ImportPage />} />
        <Route path="messages" element={<ChatView base="/seller/messages" side="store" />} />
        <Route path="messages/:id" element={<ChatView base="/seller/messages" side="store" />} />
        <Route path="reservations" element={<SellerReservationsPage />} />
        <Route path="analytics" element={<SellerAnalyticsPage />} />
        <Route path="profile" element={<ProfileSection />} />
        <Route path="*" element={<Navigate to="/seller" replace />} />
      </Route>

      <Route element={<AdminAuthLayout />}>
        <Route path="/admin/login" element={<GuestOnly><AdminLoginPage /></GuestOnly>} />
      </Route>
      <Route path="/admin" element={<AdminOnly><AdminLayout /></AdminOnly>}>
        <Route index element={<AdminOverview />} />
        <Route path="stores" element={<AdminStores />} />
        <Route path="stores/:id" element={<AdminStoreCard />} />
        <Route path="reports" element={<AdminReports />} />
        <Route path="flags" element={<AdminFlags />} />
        <Route path="fixes" element={<AdminFixes />} />
        <Route path="barcodes" element={<AdminBarcodes />} />
        <Route path="channels" element={<AdminChannels />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="log" element={<AdminLog />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Route>
    </Routes>
  )
}
