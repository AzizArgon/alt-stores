import { ArrowRight, Layers, Search, ShieldAlert, Store } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { CategoryIcon } from '../components/CategoryIcon'
import { CityMenu } from '../components/Header'
import { DemoNote, PctText } from '../components/Market'
import ProductTile from '../components/ProductTile'
import { Button, Card, EmptyState, Skeleton, SkeletonCards, inputClass } from '../components/ui'
import { cityParam } from '../config/cities'
import { linkProps, sellerUrl } from '../config/sites'
import api from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { useCity } from '../services/city.jsx'
import { formatPrice, roundSum } from '../services/format'

const BIG_TILES = 2 // the most popular sections are drawn bigger
const PHONE_TILES = 8 // a phone shows the first sections, the rest after "Все разделы"
const POPULAR_COUNT = 10
const MARKET_CATEGORIES = ['ram', 'ssd', 'gpu', 'cpu']
const WHY = [
  { key: 'standard', icon: Layers },
  { key: 'compare', icon: Store },
  { key: 'fraud', icon: ShieldAlert },
]

function Hero() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const onSubmit = (e) => {
    e.preventDefault()
    navigate(q.trim() ? `/catalog?q=${encodeURIComponent(q.trim())}` : '/catalog')
  }
  return (
    <section className="rounded-xl bg-gradient-to-br from-primary to-primary-hover px-4 py-6 text-white md:px-10 md:py-9">
      <h1 className="max-w-3xl text-h2 md:text-[2.25rem] md:leading-tight">{t('home.title')}</h1>
      <p className="mt-2 hidden max-w-2xl text-sm text-white/80 sm:block md:text-base">{t('home.hint')}</p>
      <form role="search" onSubmit={onSubmit} className="mt-5 flex max-w-4xl flex-col gap-2 sm:flex-row">
        <div className="flex shrink-0 rounded-md bg-white text-ink">
          <CityMenu className="min-h-13 w-full px-3 hover:bg-surface-2" />
        </div>
        <div className="flex min-w-0 flex-1 gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" aria-hidden />
            <input type="search" enterKeyHint="search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={t('catalog.searchPlaceholder')} aria-label={t('catalog.searchPlaceholder')}
              className={`${inputClass} min-h-13 border-transparent pl-12 text-base`} />
          </div>
          <Button type="submit" size="lg" variant="secondary" className="min-h-13 border-transparent px-4 md:px-6">{t('home.searchSubmit')}</Button>
        </div>
      </form>
    </section>
  )
}

function SectionTile({ item, usdRate, big, hidden }) {
  const { t } = useTranslation()
  const from = item.min_price_usd != null && usdRate ? formatPrice(roundSum(item.min_price_usd * usdRate), 'UZS') : null
  return (
    <Link to={`/catalog?category=${item.slug}`}
      className={`group flex min-w-0 flex-col rounded-xl border border-line bg-surface p-3 shadow-card transition-shadow outline-none hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary md:p-4 ${
        big ? 'md:col-span-2 md:row-span-2 md:p-6' : ''} ${hidden ? 'max-md:hidden' : ''}`}>
      <span className={`flex items-center justify-center rounded-lg bg-primary-soft/60 text-primary ${big ? 'size-12 md:size-20' : 'size-12'}`}>
        <CategoryIcon category={item.slug} className={big ? 'size-7 md:size-11' : 'size-7'} />
      </span>
      <span className={`mt-3 font-semibold leading-snug break-words group-hover:text-primary ${big ? 'text-sm md:mt-auto md:text-h2' : 'text-sm'}`}>
        {t(`categories.${item.slug}`)}
      </span>
      <span className="mt-1 text-xs text-muted">
        {t('home.products', { count: item.products })} · {t('catalog.stores', { count: item.stores })}
      </span>
      {from && <span className={`mt-1 font-semibold ${big ? 'text-sm md:text-lg' : 'text-sm'}`}><span className="font-normal text-muted">{t('catalog.from')} ≈ </span>{from}</span>}
    </Link>
  )
}

function SectionHead({ title, hint, demo, link }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
      <div>
        <h2 className="flex flex-wrap items-center gap-2 text-h2">{title} <DemoNote show={demo} /></h2>
        {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      </div>
      {link}
    </div>
  )
}

const MoreLink = ({ to, children }) => (
  <Link to={to} className="inline-flex min-h-9 items-center gap-1 text-sm font-medium text-primary hover:underline">
    {children}<ArrowRight className="size-4" aria-hidden />
  </Link>
)

function MarketBlock() {
  const { t } = useTranslation()
  const [data, setData] = useState(null)
  useEffect(() => {
    api.get('/market/overview', { params: { period: 'quarter' } }).then((res) => setData(res.data)).catch(() => {})
  }, [])
  const rows = MARKET_CATEGORIES.map((c) => data?.indices.rows.find((r) => r.category === c)).filter(Boolean)
  return (
    <Card as="section" className="min-w-0">
      <SectionHead title={t('home.marketTitle')} hint={t('home.marketHint')} demo={data?.includes_demo}
        link={<MoreLink to="/market">{t('home.marketLink')}</MoreLink>} />
      {!data ? <Skeleton className="h-20 w-full" /> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {rows.map((r) => (
            <Link key={r.category} to={`/catalog?category=${r.category}`} className="flex min-w-0 items-center gap-3 rounded-lg bg-surface-2 p-3 hover:bg-line">
              <CategoryIcon category={r.category} className="size-6 shrink-0 text-primary" />
              <span className="min-w-0">
                <span className="block truncate text-sm">{t(`categories.${r.category}`)}</span>
                <span className="text-lg"><PctText value={r.quarter} /></span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </Card>
  )
}

export default function HomePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { city, setCity } = useCity()
  const [sections, setSections] = useState(null)
  const [popular, setPopular] = useState(null)
  const [allSections, setAllSections] = useState(false)

  useEffect(() => {
    setSections(null)
    setPopular(null)
    const params = { city: cityParam(city) }
    api.get('/catalog/categories', { params }).then((res) => setSections(res.data)).catch(() => setSections({ items: [] }))
    api.get('/catalog/products', { params: { ...params, page_size: POPULAR_COUNT } })
      .then((res) => setPopular(res.data)).catch(() => setPopular({ items: [] }))
  }, [city])

  const cityEmpty = sections && sections.items.length === 0 && city !== 'all'
  // The server sorts by the number of products; "Прочее" is not a section to show off, it goes last
  const tiles = sections ? [...sections.items.filter((s) => s.slug !== 'other'), ...sections.items.filter((s) => s.slug === 'other')] : []

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:gap-10">
      <Hero />

      <section>
        <SectionHead title={t('home.sections')} demo={sections?.includes_demo}
          hint={city !== 'all' ? t('catalog.inCity', { city: t(`cities.${city}`) }) : undefined}
          link={<MoreLink to="/catalog">{t('home.allCatalog')}</MoreLink>} />
        {!sections && <SkeletonCards count={8} className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6" />}
        {cityEmpty && (
          <Card>
            <EmptyState title={t('catalog.cityEmpty', { city: t(`cities.${city}`) })} hint={t('catalog.cityEmptyHint')}>
              <Button onClick={() => setCity('all')}>{t('catalog.showCountry')}</Button>
            </EmptyState>
          </Card>
        )}
        {sections?.items.length > 0 && (
          <div className="grid grid-flow-dense grid-cols-2 gap-3 md:grid-cols-4 md:gap-4 lg:grid-cols-6">
            {tiles.map((item, i) => (
              <SectionTile key={item.slug} item={item} usdRate={sections.usd_rate} big={i < BIG_TILES}
                hidden={!allSections && i >= PHONE_TILES} />
            ))}
          </div>
        )}
        {!allSections && tiles.length > PHONE_TILES && (
          <Button variant="secondary" className="mt-3 w-full md:hidden" onClick={() => setAllSections(true)}>
            {t('home.allSections', { count: tiles.length })}
          </Button>
        )}
      </section>

      {!cityEmpty && (
        <section className="min-w-0">
          <SectionHead title={t('home.popular')} hint={t('home.popularHint')} demo={sections?.includes_demo}
            link={<MoreLink to="/catalog">{t('home.allCatalog')}</MoreLink>} />
          {!popular ? <SkeletonCards count={5} className="grid grid-cols-2 gap-3 md:grid-cols-5" /> : (
            // Phone: a horizontal strip that scrolls by itself (the page does not); bigger screens: a grid
            <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-4 md:gap-4 md:overflow-visible md:px-0 lg:grid-cols-5">
              {popular.items.map((item) => (
                <ProductTile key={item.id} item={item} usdRate={popular.usd_rate} rateDate={popular.usd_rate_date}
                  className="w-40 shrink-0 snap-start md:w-auto" />
              ))}
            </div>
          )}
        </section>
      )}

      <MarketBlock />

      <section>
        <SectionHead title={t('home.whyTitle')} />
        <div className="grid gap-3 md:grid-cols-3 md:gap-4">
          {WHY.map(({ key, icon: Icon }) => (
            <Card key={key}>
              <span className="flex size-11 items-center justify-center rounded-lg bg-accent-soft text-above"><Icon className="size-6" aria-hidden /></span>
              <h3 className="mt-3 text-h3">{t(`home.why.${key}`)}</h3>
              <p className="mt-1 text-sm text-muted">{t(`home.why.${key}Text`)}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col items-start gap-4 rounded-xl border border-line bg-surface p-5 shadow-card md:flex-row md:items-center md:justify-between md:p-8">
        <div className="max-w-2xl">
          <h2 className="text-h2">{t('home.sellerTitle')}</h2>
          <p className="mt-1 text-sm text-muted md:text-base">{t('home.sellerText')}</p>
        </div>
        <Button {...linkProps(user?.role === 'seller' ? sellerUrl() : sellerUrl('/register'))} size="lg" className="w-full shrink-0 md:w-auto">
          {user?.role === 'seller' ? t('nav.myCabinet') : t('home.sellerCta')}<ArrowRight className="size-4" aria-hidden />
        </Button>
      </section>
    </div>
  )
}
