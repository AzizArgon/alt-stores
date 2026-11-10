import { BadgeCheck, ExternalLink, MapPin, Phone, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import { WriteButton } from '../components/Chat'
import { BranchAvailability } from '../components/BranchList'
import { MapButtons, StoreName } from '../components/StoreWhere'
import { ReserveButton } from '../components/Reservation'
import { ProductVisual } from '../components/CategoryIcon'
import Flags from '../components/Flags'
import { MarketLabel, ProductMarket } from '../components/Market'
import { Badge, Breadcrumbs, Button, Card, Skeleton, Tabs } from '../components/ui'
import api, { errorKey } from '../services/api'
import Price from '../components/Price'
import { useCity } from '../services/city.jsx'
import { cityParam } from '../config/cities'
import { formatDate, formatDayMonth, formatPrice, roundSum, telegramUrl } from '../services/format'
import { formatSpec, specLabel, specsLine } from '../services/specs'
import { defaultGroup, groupCounts } from '../services/used'

const SORTS = ['recommended', 'price']

export function Contacts({ store }) {
  const { t } = useTranslation()
  if (!store.phone && !store.telegram) return <p className="text-sm text-muted">{t('product.noContacts')}</p>
  // Big buttons: easy to hit with a finger on a phone
  const link = 'inline-flex min-h-12 items-center justify-center gap-2 rounded-md px-6 text-base font-semibold outline-none focus-visible:ring-2 focus-visible:ring-primary'
  return (
    <div className="grid gap-2 sm:flex sm:flex-wrap sm:justify-end">
      {store.phone && (
        <a href={`tel:${store.phone}`} className={`${link} border border-line-strong bg-surface hover:bg-surface-2`}>
          <Phone className="size-4" aria-hidden />{store.phone}
        </a>
      )}
      {store.telegram && (
        <a href={telegramUrl(store.telegram)} target="_blank" rel="noreferrer" className={`${link} bg-info text-white hover:opacity-90`}>
          <Send className="size-4" aria-hidden />{t('product.telegram')}
        </a>
      )}
    </div>
  )
}

// A Telegram ad: not a shop, never verified; the buyer opens the post instead of calling (phase 9)
export function AdBadge() {
  const { t } = useTranslation()
  return <Badge tone="warning"><Send className="size-3.5" aria-hidden />{t('used.adBadge')}</Badge>
}

export function OpenPost({ url, className = '' }) {
  const { t } = useTranslation()
  return (
    <a href={url} target="_blank" rel="noreferrer nofollow"
      className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-line-strong bg-surface px-6 text-base font-semibold outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary ${className}`}>
      <ExternalLink className="size-4" aria-hidden />{t('used.openPost')}
    </a>
  )
}

export const isAd = (offer) => offer.store.kind === 'telegram'

function OfferCard({ offer, usdRate, rateDate, market, title, city }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const { store } = offer
  const ad = isAd(offer)
  // The branch of the chosen city first (phase 12.1), else the store's main address
  const first = offer.stock?.branches?.[0]
  const where = first && !ad ? { ...store, ...first, id: store.id, name: store.name, phone: store.phone } : store
  const place = [t(`cities.${where.city}`), where.district, where.address].filter(Boolean).join(', ')

  return (
    <Card as="li" padded={false} className={`min-w-0 p-4 ${offer.is_in_stock ? '' : 'opacity-60'}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-h3">
            <StoreName store={store} />
            {store.is_verified && <Badge tone="success"><BadgeCheck className="size-3.5" aria-hidden />{t('product.verified')}</Badge>}
            {ad && <AdBadge />}
          </p>
          <p className="mt-0.5 flex gap-1 text-sm text-muted"><MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />{place}</p>
          {!ad && where.hours && <p className="mt-0.5 pl-5 text-sm text-muted">{where.hours}</p>}
          <p className="mt-1.5 flex flex-wrap gap-x-2 gap-y-1 text-sm">
            <span className={offer.is_in_stock ? 'font-medium text-success' : 'text-muted'}>
              {t(offer.is_in_stock ? 'product.inStock' : 'product.outOfStock')}
            </span>
            <span className="text-faint">·</span>{t(`condition.${offer.condition}`)}
            <span className="text-faint">·</span><span className="text-muted">
              {ad ? t('used.posted', { date: formatDate(offer.posted_at) }) : t('product.updated', { date: formatDate(offer.updated_at) })}
            </span>
          </p>
          {!ad && <BranchAvailability stock={offer.stock} city={city} />}
          {offer.note && <p className="mt-1 text-sm text-muted">{offer.note}</p>}
          <p className="mt-1 text-xs break-words text-faint" title={offer.raw_name}>{offer.raw_name}</p>
        </div>
        <div className="shrink-0 sm:text-right">
          <Price price={offer.price} currency={offer.currency} usdRate={usdRate} rateDate={rateDate} />
          {offer.is_in_stock && <div className="mt-1"><MarketLabel info={market} /></div>}
        </div>
      </div>
      <Flags flags={offer.flags} className="mt-3 grid gap-1" />
      <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap sm:items-start sm:justify-end">
        {ad ? <OpenPost url={offer.post_url} className="w-full sm:w-auto" /> : <>
          <ReserveButton store={store} usdRate={usdRate} className="w-full sm:w-auto" item={{
            kind: 'offer', id: offer.id, title, condition: offer.condition, price: offer.price, currency: offer.currency,
            inStock: offer.is_in_stock }} />
          <WriteButton kind="offer" id={offer.id} store={store} className="w-full sm:w-auto" />
          <MapButtons store={where} size="lg" className="[&>a]:w-full sm:[&>a]:w-auto" />
          {open ? <Contacts store={store} />
            : <Button size="lg" className="w-full sm:w-auto" onClick={() => setOpen(true)}>{t('product.contact')}</Button>}
        </>}
      </div>
    </Card>
  )
}

function OfferList({ offers, product }) {
  const { city } = useCity()
  return (
    <ul className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {offers.map((o) => (
        <OfferCard key={o.id} offer={o} usdRate={product.usd_rate} rateDate={product.usd_rate_date} market={product.market?.offers[o.id]} title={product.name} city={city} />
      ))}
    </ul>
  )
}

// Characteristics by groups: the key ones (as on the catalog tile), the rest, the classification
function SpecsTable({ product }) {
  const { t } = useTranslation()
  const specs = product.specs.filter((s) => s.key !== 'brand')
  const value = (s) => (s.inferred ? (
    // Not written by the seller: inferred by a rule, the reason is in the hover hint
    <span title={t(`specs.inferred.${s.inferred}`)} className="cursor-help border-b border-dotted border-faint">
      {formatSpec(s)}<sup className="text-faint">*</sup>
    </span>
  ) : formatSpec(s))
  const groups = [
    { title: t('product.specsMain'), rows: [
      ...(product.brand ? [{ key: 'brand', label: t('product.brand'), value: product.brand }] : []),
      ...specs.filter((s) => s.main).map((s) => ({ key: s.key, label: specLabel(s.key, product.category), value: value(s) })),
    ] },
    { title: t('product.specsOther'), rows: specs.filter((s) => !s.main).map((s) => ({ key: s.key, label: specLabel(s.key, product.category), value: value(s) })) },
    { title: t('product.specsCatalog'), rows: [
      { key: 'category', label: t('product.category'), value: t(`categories.${product.category}`) },
      ...(product.mxik_code ? [{ key: 'mxik', label: t('product.mxik'), value: product.mxik_code }] : []),
    ] },
  ].filter((g) => g.rows.length)

  return (
    <Card as="section" className="min-w-0">
      <h2 className="text-h2">{t('product.specsTitle')}</h2>
      {groups.map((g) => (
        <div key={g.title} className="mt-4">
          <h3 className="text-sm font-semibold text-muted">{g.title}</h3>
          <dl className="mt-1 text-sm">
            {g.rows.map((r) => (
              <div key={r.key} className="grid grid-cols-2 gap-4 border-b border-line py-2 last:border-0">
                <dt className="text-muted">{r.label}</dt>
                <dd className="break-words">{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      {specs.some((s) => s.inferred) && <p className="mt-3 text-xs text-faint">{t('product.inferredNote')}</p>}
      {product.suspect?.length > 0 && (
        <p className="mt-3 rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-sm text-warning"
          title={product.suspect.map((s) => `${specLabel(s.key, product.category)}: ${formatSpec(s)}`).join(', ')}>
          {t('product.specsNeedCheck')}
        </p>
      )}
    </Card>
  )
}

// Sums of the offers in stock: "от … до …" (the seller's currency converted by the CBU rate)
function priceRange(offers, usdRate) {
  const sums = offers.filter((o) => o.is_in_stock && o.price_uzs != null).map((o) => o.price_uzs)
  if (!sums.length) return null
  const [min, max] = [Math.min(...sums), Math.max(...sums)].map((v) => (usdRate ? roundSum(v) : v))
  return { min, max, stores: new Set(offers.filter((o) => o.is_in_stock).map((o) => o.store.id)).size }
}

export default function ProductPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const { city, setCity } = useCity()
  const [sort, setSort] = useState('recommended')
  const [tab, setTab] = useState(null) // "new" / "used"; by default "new", or "used" when there are no new ones
  const [product, setProduct] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    // The city (phase 12.1): "в наличии" and "есть в N из M филиалов" by the branches of that city
    api.get(`/catalog/products/${id}`, { params: { sort, city: cityParam(city) } })
      .then((res) => { setProduct(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
  }, [id, sort, city, t])

  if (error) return <ErrorText>{error}</ErrorText>
  if (!product) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-56 w-full rounded-xl" />
        <Skeleton className="h-36 w-full rounded-xl" />
      </div>
    )
  }
  const counts = groupCounts(product.offers)
  const group = tab || defaultGroup(counts)
  const offers = product.offers.filter((o) => o.group === group)
  const byCity = city !== 'all'
  // A store is in the city when one of its branches is there
  const inCity = (o) => o.in_city || o.store.city === city
  const here = byCity ? offers.filter(inCity) : offers
  const elsewhere = byCity ? offers.filter((o) => !inCity(o)) : []
  const range = priceRange(here, product.usd_rate)
  const cityName = t(`cities.${city}`)
  const keySpecs = product.specs.filter((s) => s.main)
  const market = product.market?.conditions?.[group === 'new' ? 'new' : 'used']

  return (
    <section>
      <Breadcrumbs items={[
        { to: '/', label: t('catalog.home') },
        { to: `/catalog?category=${product.category}`, label: t(`categories.${product.category}`) },
        { label: product.name },
      ]} />

      <Card className="mt-3 flex flex-col gap-4 sm:flex-row sm:gap-6">
        <ProductVisual category={product.category} image={product.image} alt={product.name}
          className="aspect-[5/2] w-full sm:aspect-square sm:w-44 md:w-56" iconClassName="size-1/2 max-h-20 max-w-20 md:max-h-24 md:max-w-24" />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted">{t(`categories.${product.category}`)}{product.brand && ` · ${product.brand}`}</p>
          <h1 className="mt-1 text-h2 break-words md:text-h1">{product.name}</h1>
          {keySpecs.length > 0 && <p className="mt-1 text-sm break-words text-muted">{specsLine(keySpecs)}</p>}
          <div className="mt-4 flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="text-xs text-muted">
                {byCity ? t('product.priceIn', { city: cityName }) : t('product.priceAll')} · {t(`used.group.${group}`)}
              </p>
              {range ? (
                <p className="text-h2 md:text-h1">
                  {range.min === range.max ? formatPrice(range.min, 'UZS')
                    : t('product.priceRange', { from: formatPrice(range.min, 'UZS'), to: formatPrice(range.max, 'UZS') })}
                </p>
              ) : <p className="text-h3 text-muted">{byCity ? t('product.noneInCity', { city: cityName }) : '—'}</p>}
              {range && <p className="text-sm text-muted">{t('catalog.stores', { count: range.stores })}</p>}
            </div>
            {market?.market_usd != null && product.usd_rate && (
              <div className="text-sm">
                <p className="text-xs text-muted">{t('market.productTitle')} · {t('market.scope')}</p>
                <p className="font-semibold" title={t('market.scopeHint')}>≈ {formatPrice(roundSum(market.market_usd * product.usd_rate), 'UZS')}</p>
                {market.ads > 0 && <p className="text-xs text-muted">{t('used.byAds', { count: market.ads })}</p>}
              </div>
            )}
          </div>
        </div>
      </Card>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0">
          <Tabs value={group} onChange={setTab} className="mb-4"
            tabs={['new', 'used'].map((g) => ({ value: g, label: `${t(`used.group.${g}`)} (${counts[g]})` }))} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-h2">{byCity ? t('product.inCityTitle', { city: cityName }) : t('product.allTitle')}</h2>
            <Tabs value={sort} onChange={setSort} tabs={SORTS.map((s) => ({ value: s, label: t(`product.sort.${s}`) }))} />
          </div>
          {sort === 'recommended' && <p className="mt-1 text-sm text-muted">{t('product.recommendedHint')}</p>}
          {product.usd_rate && (
            <p className="mt-1 text-sm text-muted">{t('price.rateNote', { date: formatDayMonth(product.usd_rate_date), rate: formatPrice(product.usd_rate, 'UZS') })}</p>
          )}
          <div className="mt-4">
            {here.length > 0 ? <OfferList offers={here} product={product} /> : (
              <Card className="text-center">
                <p className="text-h3">{t('product.noneInCity', { city: cityName })}</p>
                <Button variant="secondary" className="mt-3" onClick={() => setCity('all')}>{t('catalog.showCountry')}</Button>
              </Card>
            )}
          </div>
          {elsewhere.length > 0 && (
            <>
              <h2 className="mt-8 mb-4 text-h2">{t('product.otherCities')} <span className="text-muted">({elsewhere.length})</span></h2>
              <OfferList offers={elsewhere} product={product} />
            </>
          )}
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
          <ProductMarket market={product.market} usdRate={product.usd_rate} condition={group === 'new' ? 'new' : 'used'} />
          <SpecsTable product={product} />
        </div>
      </div>
    </section>
  )
}
