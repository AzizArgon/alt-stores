import { SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import { Sheet } from '../components/overlays'
import { Button, Card, Checkbox, EmptyState, Input, Pagination, Select, SkeletonCards } from '../components/ui'
import api, { errorKey } from '../services/api'
import Price from '../components/Price'
import { formatDayMonth, formatPrice } from '../services/format'
import { formatSpec, fromUrlValue, specLabel, specsLine, urlValue } from '../services/specs'

const CONDITIONS = ['new', 'new_openbox', 'used', 'refurbished', 'unknown']

const VISIBLE_VALUES = 8
const SPEC_PREFIX = 'f_' // spec filters in the address: ?category=ram&f_type=DDR5,DDR4&f_form_factor=SODIMM

function ProductTile({ item, usdRate, rateDate }) {
  const { t } = useTranslation()
  return (
    <Link to={`/products/${item.id}`}
      className="flex min-w-0 flex-col rounded-xl border border-line bg-surface p-3 shadow-card transition-shadow hover:shadow-hover md:p-4">
      <span className="text-xs text-muted">{t(`categories.${item.category}`)}</span>
      <span className="mt-1 line-clamp-3 text-sm font-semibold leading-snug break-words md:text-base">{item.name}</span>
      {item.specs?.length > 0 && <span className="mt-1 line-clamp-3 text-xs break-words text-muted md:text-sm">{specsLine(item.specs)}</span>}
      <div className="mt-auto pt-3">
        <Price price={item.min_price} currency={item.min_currency} usdRate={usdRate} rateDate={rateDate}
          prefix={`${t('catalog.from')} `} size="text-base md:text-lg" />
        <span className="mt-1 block text-xs text-muted">{t('catalog.offers', { count: item.offers })}</span>
      </div>
    </Link>
  )
}

// One filter of the category: ticks with counts ("DDR5 (124)"), or "from N" for refresh rate and power
function Facet({ facet, category, selected, onToggle, onAtLeast }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const label = specLabel(facet.key, category)
  const format = (value) => formatSpec({ ...facet, value })

  if (facet.at_least) {
    // "from 144 Hz" counts every product with 144 Hz and more
    const atLeast = (v) => facet.values.filter((x) => x.value >= v).reduce((sum, x) => sum + x.count, 0)
    return (
      <div>
        <Select label={label} value={selected[0] || ''} onChange={(e) => onAtLeast(e.target.value)}>
          <option value="">{t('catalog.any')}</option>
          {facet.values.map(({ value }) => (
            <option key={value} value={urlValue(value)}>{t('catalog.atLeast', { value: format(value) })} ({atLeast(value)})</option>
          ))}
        </Select>
      </div>
    )
  }
  const values = open ? facet.values : facet.values.slice(0, VISIBLE_VALUES)
  return (
    <div>
      <p className="mb-1 text-sm font-semibold">{label}</p>
      {values.map(({ value, count }) => (
        <Checkbox key={urlValue(value)} checked={selected.includes(urlValue(value))} onChange={() => onToggle(urlValue(value))}
          label={<>{format(value)} <span className="text-faint">({count})</span></>} />
      ))}
      {facet.values.length > VISIBLE_VALUES && (
        <button onClick={() => setOpen(!open)} className="mt-1 text-sm font-medium text-primary hover:underline">
          {open ? t('catalog.showLess') : t('catalog.showAll', { count: facet.values.length })}
        </button>
      )}
    </div>
  )
}

// All filters of the catalog: a column on a big screen, a panel from below on a phone
function FiltersPanel({ categories, category, setCategory, params, setParam, facets, selectedOf, toggleValue }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-4">
      <Select label={t('import.col.category')} value={category} onChange={(e) => setCategory(e.target.value)}>
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
      <Select label={t('import.col.condition')} value={params.get('condition') || ''} onChange={(e) => setParam('condition', e.target.value, true)}>
        <option value="">{t('catalog.anyCondition')}</option>
        {CONDITIONS.map((c) => <option key={c} value={c}>{t(`condition.${c}`)}</option>)}
      </Select>
      <Checkbox label={t('catalog.inStockOnly')} checked={!params.get('all')} onChange={(e) => setParam('all', e.target.checked ? '' : '1', true)} />
      {facets.map((f) => (
        <Facet key={f.key} facet={f} category={category} selected={selectedOf(f.key)}
          onToggle={(v) => toggleValue(f.key, v)} onAtLeast={(v) => setParam(SPEC_PREFIX + f.key, v, true)} />
      ))}
    </div>
  )
}

export default function CatalogPage() {
  const { t } = useTranslation()
  // Filters live in the URL: "back" from a product card returns to the same search
  const [params, setParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [categories, setCategories] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const category = params.get('category') || ''

  // Ticks add a history step (browser "back" undoes them); typing in a field replaces the current one
  const update = (change, push = false) => {
    const next = new URLSearchParams(params)
    change(next)
    next.delete('page')
    setParams(next, { replace: !push })
  }
  const setParam = (key, value, push = false) => update((next) => {
    if (value === '' || value == null) next.delete(key)
    else next.set(key, value)
  }, push)
  const specKeys = [...params.keys()].filter((k) => k.startsWith(SPEC_PREFIX))
  const selectedOf = (key) => (params.get(SPEC_PREFIX + key) || '').split(',').filter(Boolean)

  const setCategory = (slug) => update((next) => {
    specKeys.forEach((k) => next.delete(k)) // filters of one category mean nothing in another
    if (slug) next.set('category', slug)
    else next.delete('category')
  }, true)
  const toggleValue = (key, value) => update((next) => {
    const current = selectedOf(key)
    const values = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
    if (values.length) next.set(SPEC_PREFIX + key, values.join(','))
    else next.delete(SPEC_PREFIX + key)
  }, true)
  const resetFilters = () => update((next) => {
    specKeys.forEach((k) => next.delete(k))
    next.delete('price_min')
    next.delete('price_max')
  }, true)

  useEffect(() => {
    api.get('/categories').then((res) => setCategories(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const req = Object.fromEntries(params)
    req.in_stock = params.get('all') ? 'false' : 'true'
    delete req.all
    api.get('/catalog/products', { params: req })
      .then((res) => { setData(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
  }, [params, t])

  const page = data?.page || 1
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const facets = (category && data?.facets) || []

  // Chips of everything selected, each removes its own value
  const chips = specKeys.flatMap((k) => {
    const key = k.slice(SPEC_PREFIX.length)
    const facet = facets.find((f) => f.key === key) || { key, kind: 'choice' }
    return selectedOf(key).map((v) => {
      const value = formatSpec({ ...facet, value: fromUrlValue(facet.kind, v) })
      return {
        id: `${k}=${v}`,
        text: `${specLabel(key, category)}: ${facet.at_least ? t('catalog.atLeast', { value }) : value}`,
        remove: () => toggleValue(key, v),
      }
    })
  })
  for (const [k, word] of [['price_min', 'priceMin'], ['price_max', 'priceMax']]) {
    if (params.get(k)) {
      chips.push({ id: k, text: `${t('catalog.price')}: ${t(`catalog.${word}`)} ${formatPrice(Number(params.get(k)), 'UZS')}`,
        remove: () => setParam(k, '', true) })
    }
  }

  const activeFilters = chips.length + ['category', 'condition', 'all'].filter((k) => params.get(k)).length
  const filters = (
    <FiltersPanel categories={categories} category={category} setCategory={setCategory} params={params} setParam={setParam}
      facets={facets} selectedOf={selectedOf} toggleValue={toggleValue} />
  )

  return (
    <section>
      <h1 className="text-h2 md:text-h1">{t('app.tagline')}</h1>
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <div className="flex items-start gap-6">
        <aside className="hidden w-64 shrink-0 lg:block" aria-label={t('catalog.filters')}>
          <Card padded={false} className="p-4">{filters}</Card>
        </aside>
        <div className="min-w-0 flex-1">
          <Button variant="secondary" className="mb-3 w-full lg:hidden" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal className="size-4" aria-hidden />
            {activeFilters ? t('catalog.filtersActive', { count: activeFilters }) : t('catalog.filters')}
          </Button>
          <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title={t('catalog.filters')}
            footer={<Button className="w-full" onClick={() => setFiltersOpen(false)}>{t('catalog.show')}{data && ` (${data.total})`}</Button>}>
            {filters}
          </Sheet>
          {chips.length > 0 && (
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {chips.map((c) => (
                <button key={c.id} onClick={c.remove}
                  className="inline-flex max-w-full items-center gap-1 rounded-full bg-primary-soft px-3 py-1 text-left text-sm font-medium text-primary hover:bg-line">
                  <span className="min-w-0">{c.text}</span><X className="size-3.5 shrink-0" aria-hidden />
                </button>
              ))}
              <button onClick={resetFilters} className="text-sm font-medium text-muted hover:text-ink hover:underline">{t('catalog.reset')}</button>
            </div>
          )}
          {!data && !error && <SkeletonCards count={9} />}
          {data && (
            <>
              <p className="text-sm text-muted">
                {t('catalog.found', { count: data.total })}
                {data.usd_rate && <> · {t('price.rateNote', { date: formatDayMonth(data.usd_rate_date), rate: formatPrice(data.usd_rate, 'UZS') })}</>}
              </p>
              {data.items.length === 0 ? (
                <EmptyState title={t('catalog.empty')} hint={t('catalog.emptyHint')} />
              ) : (
                <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4">
                  {data.items.map((item) => <ProductTile key={item.id} item={item} usdRate={data.usd_rate} rateDate={data.usd_rate_date} />)}
                </div>
              )}
              <Pagination className="mt-6" page={page} pages={pages} onChange={(n) => {
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
