import { SlidersHorizontal } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import BuildTile from '../components/BuildTile'
import { Sheet } from '../components/overlays'
import { Breadcrumbs, Button, Card, Checkbox, EmptyState, Input, Pagination, Select, SkeletonCards, Tabs } from '../components/ui'
import { cityParam } from '../config/cities'
import api, { errorKey } from '../services/api'
import { useCity } from '../services/city.jsx'
import { formatDayMonth, formatPrice } from '../services/format'
import { useSpecDictionary } from '../services/specs'

const SORTS = ['new', 'price_asc', 'price_desc']
// Ticks with counts; the value text of each filter
const FACETS = [
  { key: 'purpose', label: 'builds.purposeLabel', text: (t, v) => t(`builds.purpose.${v}`) },
  { key: 'cpu', label: 'builds.cpuLabel', text: (t, v) => (v === 'intel' ? 'Intel' : 'AMD') },
  { key: 'gpu', label: 'builds.gpuLabel', text: (t, v) => (v === 'integrated' ? t('builds.integrated') : v) },
  { key: 'ram', label: 'builds.ramLabel', text: (t, v) => t('builds.ramValue', { value: v }) },
  { key: 'condition', label: 'builds.conditionLabel', text: (t, v) => t(`builds.condition.${v}`) },
]

function FiltersPanel({ params, setParam, facets, selectedOf, toggle }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-4">
      <div>
        <p className="mb-1.5 text-sm font-medium">{t('builds.price')}</p>
        <div className="grid grid-cols-2 gap-2">
          <Input type="number" min="0" step="1000000" aria-label={t('builds.priceMin')} placeholder={t('builds.priceMin')}
            value={params.get('price_min') || ''} onChange={(e) => setParam('price_min', e.target.value)} />
          <Input type="number" min="0" step="1000000" aria-label={t('builds.priceMax')} placeholder={t('builds.priceMax')}
            value={params.get('price_max') || ''} onChange={(e) => setParam('price_max', e.target.value)} />
        </div>
      </div>
      <div>
        <Checkbox label={t('builds.exactOnly')} checked={Boolean(params.get('exact_only'))}
          onChange={(e) => setParam('exact_only', e.target.checked ? '1' : '', true)} />
        <p className="mt-0.5 pl-7 text-xs text-muted">{t('builds.exactOnlyHint')}</p>
      </div>
      {FACETS.map(({ key, label, text }) => (facets?.[key]?.length > 0 || selectedOf(key).length > 0) && (
        <div key={key}>
          <p className="mb-1 text-sm font-semibold">{t(label)}</p>
          {(facets?.[key] || []).map(({ value, count }) => (
            <Checkbox key={value} checked={selectedOf(key).includes(String(value))} onChange={() => toggle(key, String(value))}
              label={<>{text(t, value)} <span className="text-faint">({count})</span></>} />
          ))}
        </div>
      ))}
    </div>
  )
}

export default function BuildsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const { city, setCity } = useCity()
  const dictionary = useSpecDictionary()
  const sort = params.get('sort') || 'new'

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
  const selectedOf = (key) => (params.get(key) || '').split(',').filter(Boolean)
  const toggle = (key, value) => update((next) => {
    const current = selectedOf(key)
    const values = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
    if (values.length) next.set(key, values.join(','))
    else next.delete(key)
  }, true)
  const reset = () => setParams(sort === 'new' ? {} : { sort })

  useEffect(() => {
    const req = { ...Object.fromEntries(params), city: cityParam(city) }
    if (req.exact_only) req.exact_only = 'true'
    setLoading(true)
    api.get('/builds', { params: req })
      .then((res) => { setData(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
      .finally(() => setLoading(false))
  }, [params, city, t])

  const active = ['price_min', 'price_max', 'exact_only', ...FACETS.map((f) => f.key)].filter((k) => params.get(k)).length
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const cityName = t(`cities.${city}`)
  const filters = <FiltersPanel params={params} setParam={setParam} facets={data?.facets} selectedOf={selectedOf} toggle={toggle} />

  return (
    <section>
      <Breadcrumbs items={[{ to: '/', label: t('catalog.home') }, { label: t('builds.title') }]} />
      <h1 className="mt-2 text-h2 md:text-h1">{t('builds.title')}</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">{t('builds.subtitle')}</p>
      {city !== 'all' && <p className="mt-1 text-sm text-muted">{t('catalog.inCity', { city: cityName })}</p>}
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <div className="flex items-start gap-6">
        <aside className="hidden w-64 shrink-0 lg:block" aria-label={t('builds.filters')}>
          <Card padded={false} className="p-4">
            {filters}
            {active > 0 && <button onClick={reset} className="mt-4 text-sm font-medium text-muted hover:text-ink hover:underline">{t('builds.reset')}</button>}
          </Card>
        </aside>
        <div className="min-w-0 flex-1">
          <Button className="fixed bottom-4 left-1/2 z-20 -translate-x-1/2 rounded-full shadow-pop lg:hidden" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal className="size-4" aria-hidden />
            {active ? t('builds.filtersActive', { count: active }) : t('builds.filters')}
          </Button>
          <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title={t('builds.filters')}
            footer={<Button className="w-full" onClick={() => setFiltersOpen(false)}>{t('builds.show')}{data && ` (${data.total})`}</Button>}>
            {filters}
            {active > 0 && <button onClick={reset} className="mt-4 text-sm font-medium text-muted hover:underline">{t('builds.reset')}</button>}
          </Sheet>
          {!data && !error && <SkeletonCards count={6} />}
          {data && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted">
                  {t('builds.found', { count: data.total })}
                  {data.usd_rate && <span className="hidden sm:inline"> · {t('price.rateNote', { date: formatDayMonth(data.usd_rate_date), rate: formatPrice(data.usd_rate, 'UZS') })}</span>}
                </p>
                <Tabs className="hidden sm:inline-flex" label={t('builds.sortLabel')} value={sort} onChange={(v) => setParam('sort', v === 'new' ? '' : v, true)}
                  tabs={SORTS.map((s) => ({ value: s, label: t(`builds.sort.${s}`) }))} />
                <Select className="w-full sm:hidden" aria-label={t('builds.sortLabel')} value={sort} onChange={(e) => setParam('sort', e.target.value === 'new' ? '' : e.target.value, true)}>
                  {SORTS.map((s) => <option key={s} value={s}>{t('builds.sortLabel')}: {t(`builds.sort.${s}`)}</option>)}
                </Select>
              </div>
              {data.items.length === 0 ? (
                <EmptyState title={city !== 'all' && !active ? t('builds.cityEmpty', { city: cityName }) : t('builds.empty')}
                  hint={city !== 'all' && !active ? t('builds.cityEmptyHint') : t('builds.emptyHint')}>
                  {city !== 'all' && <Button onClick={() => setCity('all')}>{t('builds.showCountry')}</Button>}
                </EmptyState>
              ) : (
                <div aria-busy={loading} className={`mt-4 grid grid-cols-1 gap-3 transition-opacity sm:grid-cols-2 md:gap-4 xl:grid-cols-3 ${loading ? 'opacity-50' : ''}`}>
                  {data.items.map((item) => <BuildTile key={item.id} item={item} dictionary={dictionary} usdRate={data.usd_rate} rateDate={data.usd_rate_date} />)}
                </div>
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
