import { useTranslation } from 'react-i18next'
import { Outlet, useLocation } from 'react-router-dom'
import Footer from '../components/Footer'
import Header from '../components/Header'
import SearchBar, { SEARCH_ROW_PATHS } from '../components/SearchBar'

// Set only for the public server build (deploy.bat)
const PUBLIC_DEMO = import.meta.env.VITE_PUBLIC_DEMO === '1'

export function DemoBanner() {
  const { t } = useTranslation()
  if (!PUBLIC_DEMO) return null
  return (
    <div className="bg-ink px-4 py-1.5 text-center text-xs text-white/85">
      {t('demo.banner')}
    </div>
  )
}

// The storefront for buyers: a light header, the search row (words + city) on the home page and in the catalog, footer
export default function StoreLayout() {
  const { pathname } = useLocation()
  return (
    <div className="flex min-h-screen flex-col">
      {/* Phase 16.2: the header is the first thing at the top (iPhone: it covers the status bar area), the demo line under it */}
      <Header />
      <DemoBanner />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6 md:py-8">
        {SEARCH_ROW_PATHS.includes(pathname) && <SearchBar className="mb-6 md:mb-8" />}
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
