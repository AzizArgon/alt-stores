import { ArrowRight, Store } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CategoryIcon } from '../components/CategoryIcon'
import { DemoNote, PctText } from '../components/Market'
import BuildTile from '../components/BuildTile'
import ProductTile from '../components/ProductTile'
import SearchBar from '../components/SearchBar'
import { Button, Card, EmptyState, Skeleton, SkeletonCards } from '../components/ui'
import { cityParam } from '../config/cities'
import { groupLayout, groupSections, sideTileClass } from '../config/homeGroups'
import api from '../services/api'
import { useCity } from '../services/city.jsx'
import { formatPrice, roundSum } from '../services/format'
import { useSpecDictionary } from '../services/specs'

const PHONE_TILES = 8 // a phone shows the first groups, the rest after "Все разделы"
const POPULAR_COUNT = 10
const BUILDS_COUNT = 4
const MARKET_CATEGORIES = ['ram', 'ssd', 'gpu', 'cpu']

// Phase 16.2: every tile is the same — icon, name, "от ≈ … сум". Phase 17.1: one fixed height, never stretched
function SectionTile({ item, usdRate, className = '' }) {
  const { t } = useTranslation()
  const from = item.min_price_usd != null && usdRate ? formatPrice(roundSum(item.min_price_usd * usdRate), 'UZS') : null
  return (
    <Link to={`/catalog?category=${item.slug}`}
      className={`group flex h-40 min-w-0 flex-col rounded-xl border border-line bg-surface p-3 shadow-card transition-shadow outline-none hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary md:p-4 ${className}`}>
      <span className="flex size-12 items-center justify-center rounded-lg bg-primary-soft/60 text-primary">
        <CategoryIcon category={item.slug} className="size-7" />
      </span>
      <span className="mt-3 line-clamp-2 text-sm font-semibold leading-snug break-words group-hover:text-primary">{t(`categories.${item.slug}`)}</span>
      {from && <span className="mt-auto pt-1 text-sm font-semibold"><span className="font-normal text-muted">{t('catalog.from')} ≈ </span>{from}</span>}
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

// "Готовые ПК": a tall tile in the last column (laptop and wider), a strip on a phone and a tablet.
// Photos of the builds are the background, the text sits at the bottom on a dark gradient
function BuildsTile({ builds, className = '' }) {
  const { t } = useTranslation()
  const photos = (builds?.items || []).map((b) => b.image).filter(Boolean).slice(0, 2)
  return (
    <Link to="/builds"
      className={`group relative isolate flex min-h-36 min-w-0 flex-col justify-end overflow-hidden rounded-xl bg-gradient-to-br from-primary to-primary-hover text-white shadow-card outline-none transition-shadow hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${className}`}>
      {photos.length > 0 ? (
        <span className="absolute inset-0 -z-10 grid grid-cols-2 bg-white lg:grid-cols-1 lg:grid-rows-2" aria-hidden>
          {photos.map((src) => <img key={src} src={src} alt="" loading="lazy" className={`size-full min-h-0 object-cover transition-transform duration-300 group-hover:scale-105 ${photos.length === 1 ? 'col-span-2 lg:col-span-1 lg:row-span-2' : ''}`} />)}
        </span>
      ) : (
        <CategoryIcon category="desktop" className="absolute top-5 right-5 -z-10 size-20 text-white/25" />
      )}
      <span className="absolute inset-x-0 bottom-0 -z-10 h-3/4 bg-gradient-to-t from-black/85 via-black/50 to-transparent" aria-hidden />
      <span className="flex items-end gap-3 p-4 md:p-5">
        <span className="min-w-0 flex-1">
          <span className="block text-lg font-bold leading-tight md:text-xl">{t('home.buildsTitle')}</span>
          <span className="mt-1 block text-sm text-white/85">
            {t('home.buildsHint')}{builds?.total != null && ` · ${t('home.buildsCount', { count: builds.total })}`}
          </span>
        </span>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/20 transition-colors group-hover:bg-white/30">
          <ArrowRight className="size-5" aria-hidden />
        </span>
      </span>
    </Link>
  )
}

// The groups of sections; the first group carries the tall "Готовые ПК" tile
function SectionGroups({ groups, usdRate, builds, showAll }) {
  const { t } = useTranslation()
  // How many tiles come before each group: a phone shows the groups that start within the first PHONE_TILES
  const starts = groups.map((_, gi) => groups.slice(0, gi).reduce((n, g) => n + g.items.length, 0))
  const layout = groupLayout(groups.map((g) => g.items.length))
  // One page grid; each group is a subgrid of it, so small groups stand side by side in one row
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-6 md:grid-cols-4 md:gap-x-4 md:gap-y-8 lg:grid-cols-5 xl:grid-cols-6">
      {groups.map((group, gi) => (
        <div key={group.key} className={`grid grid-flow-dense grid-cols-subgrid content-start gap-y-3 md:gap-y-4 ${layout[gi].wrap} ${
          !showAll && starts[gi] >= PHONE_TILES ? 'max-md:hidden' : ''}`}>
          <h3 className="col-span-full -mb-0.5 text-h3">{t(`home.groups.${group.key}`)}</h3>
          {group.items.map((item) => (
            <SectionTile key={item.slug} item={item} usdRate={usdRate} />
          ))}
          {gi === 0 && <BuildsTile builds={builds} className={sideTileClass(group.items.length)} />}
        </div>
      ))}
    </div>
  )
}

// Phase 16.2: the sellers' story lives on /for-sellers; the home page keeps one banner leading there
function SellerBanner() {
  const { t } = useTranslation()
  return (
    <Link to="/for-sellers"
      className="group flex items-center gap-4 rounded-xl border border-line bg-surface p-4 shadow-card outline-none transition-shadow hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary md:p-6">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-above"><Store className="size-6" aria-hidden /></span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold group-hover:text-primary md:text-lg">{t('home.sellerBanner')}</span>
        <span className="block text-sm text-muted">{t('home.sellerBannerHint')}</span>
      </span>
      <ArrowRight className="size-5 shrink-0 text-primary" aria-hidden />
    </Link>
  )
}

// Phase 17.1: the blue banner is back (as before 16.2), with the search row inside — the only search row of the home page
export function Hero() {
  const { t } = useTranslation()
  return (
    <section className="rounded-xl bg-gradient-to-br from-primary to-primary-hover px-4 py-6 text-white md:px-10 md:py-9">
      <h1 className="max-w-3xl text-h2 md:text-[2.25rem] md:leading-tight">{t('home.title')}</h1>
      <p className="mt-2 max-w-2xl text-sm text-white/85 md:text-base">{t('home.hint')}</p>
      <SearchBar variant="hero" className="mt-5 max-w-4xl" />
    </section>
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
  const { city, setCity } = useCity()
  const [sections, setSections] = useState(null)
  const [popular, setPopular] = useState(null)
  const [allSections, setAllSections] = useState(false)
  const [builds, setBuilds] = useState(null)
  const dictionary = useSpecDictionary()

  useEffect(() => {
    setSections(null)
    setPopular(null)
    setBuilds(null)
    const params = { city: cityParam(city) }
    api.get('/builds', { params: { ...params, page_size: BUILDS_COUNT } }).then((res) => setBuilds(res.data)).catch(() => setBuilds({ items: [], total: 0 }))
    api.get('/catalog/categories', { params }).then((res) => setSections(res.data)).catch(() => setSections({ items: [] }))
    api.get('/catalog/products', { params: { ...params, page_size: POPULAR_COUNT } })
      .then((res) => setPopular(res.data)).catch(() => setPopular({ items: [] }))
  }, [city])

  const cityEmpty = sections && sections.items.length === 0 && city !== 'all'
  const groups = sections ? groupSections(sections.items) : []
  const tileCount = groups.reduce((n, g) => n + g.items.length, 0)

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
        {groups.length > 0 && <SectionGroups groups={groups} usdRate={sections.usd_rate} builds={builds} showAll={allSections} />}
        {!allSections && tileCount > PHONE_TILES && (
          <Button variant="secondary" className="mt-3 w-full md:hidden" onClick={() => setAllSections(true)}>
            {t('home.allSections', { count: tileCount })}
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

      {builds?.items.length > 0 && (
        <section className="min-w-0">
          <SectionHead title={t('builds.homeTitle')} hint={t('builds.homeHint')} demo={builds.includes_demo}
            link={<MoreLink to="/builds">{t('builds.homeAll')}</MoreLink>} />
          <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-2 md:gap-4 md:overflow-visible md:px-0 lg:grid-cols-4">
            {builds.items.map((item) => (
              <BuildTile key={item.id} item={item} dictionary={dictionary} usdRate={builds.usd_rate} rateDate={builds.usd_rate_date}
                className="w-64 shrink-0 snap-start md:w-auto" />
            ))}
          </div>
        </section>
      )}

      <MarketBlock />

      <SellerBanner />
    </div>
  )
}
