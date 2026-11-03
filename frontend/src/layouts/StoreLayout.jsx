import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'
import Footer from '../components/Footer'
import Header from '../components/Header'

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

// The storefront for buyers: header with search, city and catalog; footer
export default function StoreLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <DemoBanner />
      <Header />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6 md:py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
