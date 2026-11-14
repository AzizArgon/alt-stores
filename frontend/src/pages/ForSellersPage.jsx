import { ArrowRight, BarChart3, CalendarCheck, FileSpreadsheet, MessagesSquare, ScanBarcode, Search, Warehouse } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button, Card } from '../components/ui'
import { linkProps, sellerUrl } from '../config/sites'
import { useAuth } from '../services/auth.jsx'

// Phase 16.2: what used to be two blocks of the home page is a page of its own.
// Phase 17.1: "Почему ALT STORES" went back to the home page (a thin strip); the first screen — one phrase + six perks
export const PERKS = [
  { key: 'find', icon: Search },
  { key: 'price', icon: FileSpreadsheet },
  { key: 'stock', icon: Warehouse },
  { key: 'scanner', icon: ScanBarcode },
  { key: 'chat', icon: MessagesSquare },
  { key: 'market', icon: BarChart3 },
]
export const BENEFITS = [
  { key: 'price', icon: FileSpreadsheet },
  { key: 'stock', icon: ScanBarcode },
  { key: 'buyers', icon: CalendarCheck },
  { key: 'market', icon: BarChart3 },
]
export const SELLER_REGISTER = '/register?role=seller'

function Actions({ className = '' }) {
  const { t } = useTranslation()
  const user = useAuth()?.user
  if (user?.role === 'seller') {
    return (
      <div className={className}>
        <Button {...linkProps(sellerUrl())} size="lg">{t('nav.myCabinet')}<ArrowRight className="size-4" aria-hidden /></Button>
      </div>
    )
  }
  return (
    <div className={`flex flex-col gap-2 sm:flex-row sm:flex-wrap ${className}`}>
      <Button to={SELLER_REGISTER} size="lg">{t('forSellers.register')}<ArrowRight className="size-4" aria-hidden /></Button>
      <Button to="/login" variant="secondary" size="lg">{t('forSellers.login')}</Button>
    </div>
  )
}

export default function ForSellersPage() {
  const { t } = useTranslation()
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:gap-10">
      <section className="grid gap-6 rounded-xl border border-line bg-surface p-5 shadow-card md:p-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-center lg:gap-10">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-primary">{t('footer.forSellers')}</p>
          <h1 className="mt-1 max-w-3xl text-h1 md:text-[2.25rem] md:leading-tight">{t('forSellers.title')}</h1>
          <p className="mt-3 text-muted md:text-lg">{t('forSellers.lead')}</p>
          <Actions className="mt-6" />
        </div>
        <ul className="grid gap-2.5" aria-label={t('forSellers.benefitsTitle')}>
          {PERKS.map(({ key, icon: Icon }) => (
            <li key={key} className="flex items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary"><Icon className="size-5" aria-hidden /></span>
              <span className="min-w-0 text-sm font-medium md:text-base">{t(`forSellers.perks.${key}`)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-h2">{t('forSellers.benefitsTitle')}</h2>
        <div className="grid gap-3 sm:grid-cols-2 md:gap-4">
          {BENEFITS.map(({ key, icon: Icon }) => (
            <Card key={key} className="flex gap-4">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary"><Icon className="size-6" aria-hidden /></span>
              <div className="min-w-0">
                <h3 className="text-h3">{t(`forSellers.benefit.${key}`)}</h3>
                <p className="mt-1 text-sm text-muted">{t(`forSellers.benefit.${key}Text`)}</p>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col items-start gap-4 rounded-xl bg-gradient-to-br from-primary to-primary-hover p-5 text-white md:flex-row md:items-center md:justify-between md:p-8">
        <div className="max-w-2xl">
          <h2 className="text-h2">{t('forSellers.ctaTitle')}</h2>
          <p className="mt-1 text-sm text-white/80 md:text-base">{t('forSellers.ctaText')}</p>
        </div>
        <Button to={SELLER_REGISTER} variant="secondary" size="lg" className="w-full shrink-0 border-transparent md:w-auto">
          {t('forSellers.register')}<ArrowRight className="size-4" aria-hidden />
        </Button>
      </section>
    </div>
  )
}
