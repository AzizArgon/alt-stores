import { MapPin, SlidersHorizontal } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import { WriteButton } from '../components/Chat'
import Flags from '../components/Flags'
import { Sheet } from '../components/overlays'
import Price from '../components/Price'
import { Breadcrumbs, Button, Card, Checkbox, EmptyState, Input, Pagination, Select, SkeletonCards, Tabs } from '../components/ui'
import { cityParam } from '../config/cities'
import api, { errorKey } from '../services/api'
import { useCity } from '../services/city.jsx'
import { formatDate, formatDayMonth, formatPrice } from '../services/format'
import { AdBadge, Contacts, OpenPost, isAd } from './ProductPage'

const SORTS = ['newest', 'price_asc', 'price_desc']
const CONDITIONS = ['used', 'refurbished', 'unknown']
const SOURCES = [['', 'used.sourceAny'], ['shop', 'used.sourceShop'], ['telegram', 'used.sourceTelegram']]

function FiltersPanel({ categories, params, setParam, selected, toggle }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-4">
      <Select label={t('import.col.category')} value={params.get('category') || ''} onChange={(e) => setParam('category', e.target.value, true)}>
        <option value="">{t('catalog.allCategories')}</option>
        {categories.map((c) => <option key={c.slug} value={c.slug}>{t(`categories.${c.slug}`)}</option>)}
      </Select>
      <div>
        <p className="mb-1.5 text-sm font-medium">{t('catalog.price')}</p>
        <div className="grid grid-cols-2 gap-2">
          <Input type="number" min="0" step="100000" aria-label={t('catalog.priceMin')} placeholder={t('catalog.priceMin')}
            value={params.get('price_min') || ''} onChange={(e) => setParam('price_min', e.target.value)} />
          <Input type="number" min="0" step="100000" aria-label={t('catalog.priceMax')} placeholder={t('catalog.priceMax')}
            value={params.get('price_max') || ''} onChange={(e) => setParam('price_max', e.target.value)} />
        </div>
      </div>
      <div>
        <p className="mb-1 text-sm font-semibold">{t('import.col.condition')}</p>
        {CONDITIONS.map((c) => (
          <Checkbox key={c} checked={selected.includes(c)} onChange={() => toggle(c)} label={t(`condition.${c}`)} />
        ))}
      </div>
      <Select label={t('used.source')} value={params.get('source') || ''} onChange={(e) => setParam('source', e.target.value, true)}>
        {SOURCES.map(([v, label]) => <option key={v} value={v}>{t(label)}</option>)}
      </Select>
    </div>
  )
}

// One used offer: the product, its condition, the seller (a shop or a Telegram ad), the price and the flags
function UsedOffer({ item, usdRate, rateDate }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ad = isAd(item)
  return (
    <Card as="li" padded={false} className="min-w-0 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <p className="text-xs text-muted">{t(`categories.${item.category}`)}</p>
          <Link to={`/products/${item.product_id}`} className="text-h3 break-words hover:text-primary">{item.name}</Link>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className={item.condition === 'unknown' ? 'text-warning' : 'font-medium'}
              title={item.condition === 'unknown' ? t('used.conditionNote') : undefined}>{t(`condition.${item.condition}`)}</span>
            <span className="text-faint">·</span>
            <span>{item.store.name}</span>
            {ad && <AdBadge />}
          </p>
          <p className="mt-0.5 flex gap-1 text-sm text-muted">
            <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />{t(`cities.${item.store.city}`)}
            <span className="text-faint">·</span>
            {ad ? t('used.posted', { date: formatDate(item.posted_at) }) : t('product.updated', { date: formatDate(item.updated_at) })}
          </p>
          {item.note && <p className="mt-1 text-sm text-muted">{item.note}</p>}
          <p className="mt-1 line-clamp-2 text-xs break-words text-faint" title={item.raw_name}>{item.raw_name}</p>
        </div>
        <div className="shrink-0 sm:text-right">
          <Price price={item.price} currency={item.currency} usdRate={usdRate} rateDate={rateDate} />
        </div>
      </div>
      <Flags flags={item.flags} className="mt-3 grid gap-1" />
      <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap sm:items-start sm:justify-end">
        {ad ? <OpenPost url={item.post_url} className="w-full sm:w-auto" /> : <>
          <WriteButton kind="offer" id={item.id} store={item.store} className="w-full sm:w-auto" />
          {open ? <Contacts store={item.store} />
            : <Button size="lg" className="w-full sm:w-auto" onClick={() => setOpen(true)}>{t('product.contact')}</Button>}
        </>}
      </div>
    </Card>
  )
}

export default function UsedPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [categories, setCategories] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const { city, setCity } = useCity()
  const sort = params.get('sort') || 'newest'

  const setParam = (key, value, push = false) => {
    const next = new URLSearchParams(params)
    if (value === '' || value == null) next.delete(key)
    else next.set(key, value)
    next.delete('page')
    setParams(next, { replace: !push })
  }
  const selected = (params.get('condition') || '').split(',').filter(Boolean)
  const toggle = (c) => {
    const values = selected.includes(c) ? selected.filter((v) => v !== c) : [...selected, c]
    setParam('condition', values.join(','), true)
  }
  const reset = () => setParams(sort === 'newest' ? {} : { sort })

  useEffect(() => { api.get('/categories').then((res) => setCategories(res.data)).catch(() => {}) }, [])
  useEffect(() => {
    setLoading(true)
    api.get('/catalog/used', { params: { ...Object.fromEntries(params), city: cityParam(city) } })
      .then((res) => { setData(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
      .finally(() => setLoading(false))
  }, [params, city, t])

  const active = ['category', 'price_min', 'price_max', 'condition', 'source'].filter((k) => params.get(k)).length
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const cityName = t(`cities.${city}`)
  const filters = <FiltersPanel categories={categories} params={params} setParam={setParam} selected={selected} toggle={toggle} />
  const resetButton = active > 0 && (
    <button onClick={reset} className="mt-4 text-sm font-medium text-muted hover:text-ink hover:underline">{t('builds.reset')}</button>
  )

  return (
    <section>
      <Breadcrumbs items={[{ to: '/', label: t('catalog.home') }, { label: t('used.title') }]} />
      <h1 className="mt-2 text-h2 md:text-h1">{t('used.title')}</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">{t('used.subtitle')}</p>
      {city !== 'all' && <p className="mt-1 text-sm text-muted">{t('catalog.inCity', { city: cityName })}</p>}
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <div className="flex items-start gap-6">
        <aside className="hidden w-64 shrink-0 lg:block" aria-label={t('builds.filters')}>
          <Card padded={false} className="p-4">{filters}{resetButton}</Card>
        </aside>
        <div className="min-w-0 flex-1">
          <Button className="fixed bottom-4 left-1/2 z-20 -translate-x-1/2 rounded-full shadow-pop lg:hidden" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal className="size-4" aria-hidden />
            {active ? t('builds.filtersActive', { count: active }) : t('builds.filters')}
          </Button>
          <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title={t('builds.filters')}
            footer={<Button className="w-full" onClick={() => setFiltersOpen(false)}>{t('builds.show')}{data && ` (${data.total})`}</Button>}>
            {filters}{resetButton}
          </Sheet>
          {!data && !error && <SkeletonCards count={4} />}
          {data && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted">
                  {t('used.found', { count: data.total })}
                  {data.usd_rate && <span className="hidden sm:inline"> · {t('price.rateNote', { date: formatDayMonth(data.usd_rate_date), rate: formatPrice(data.usd_rate, 'UZS') })}</span>}
                </p>
                <Tabs className="hidden sm:block" label={t('builds.sortLabel')} value={sort} onChange={(v) => setParam('sort', v === 'newest' ? '' : v, true)}
                  tabs={SORTS.map((s) => ({ value: s, label: t(`used.sort.${s}`) }))} />
                <Select className="w-full sm:hidden" aria-label={t('builds.sortLabel')} value={sort} onChange={(e) => setParam('sort', e.target.value === 'newest' ? '' : e.target.value, true)}>
                  {SORTS.map((s) => <option key={s} value={s}>{t('builds.sortLabel')}: {t(`used.sort.${s}`)}</option>)}
                </Select>
              </div>
              {data.items.length === 0 ? (
                <EmptyState title={t('used.empty')} hint={city !== 'all' ? t('builds.cityEmptyHint') : undefined}>
                  {city !== 'all' && <Button onClick={() => setCity('all')}>{t('builds.showCountry')}</Button>}
                </EmptyState>
              ) : (
                <ul aria-busy={loading} className={`mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 transition-opacity ${loading ? 'opacity-50' : ''}`}>
                  {data.items.map((item) => <UsedOffer key={item.id} item={item} usdRate={data.usd_rate} rateDate={data.usd_rate_date} />)}
                </ul>
              )}
              <Pagination className="mt-6" page={data.page} pages={pages} onChange={(n) => {
                setParams((prev) => { prev.set('page', n); return prev })
                window.scrollTo(0, 0)
              }} />
            </>
          )}
        </div>
      </div>
    </section>
  )
}
