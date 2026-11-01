import { ArrowLeft, BadgeCheck, Phone, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import Flags from '../components/Flags'
import { MarketLabel, ProductMarket } from '../components/Market'
import { Badge, Button, Card, Skeleton, Tabs } from '../components/ui'
import api, { errorKey } from '../services/api'
import Price from '../components/Price'
import { formatDate, formatDayMonth, formatPrice, telegramUrl } from '../services/format'
import { formatSpec, specLabel } from '../services/specs'

const SORTS = ['recommended', 'price']

function Contacts({ store }) {
  const { t } = useTranslation()
  if (!store.phone && !store.telegram) return <p className="text-sm text-muted">{t('product.noContacts')}</p>
  return (
    <div className="flex flex-col gap-1 text-sm md:items-end">
      {store.phone && <a href={`tel:${store.phone}`} className="font-medium hover:underline"><Phone className="mr-1 inline size-4" aria-hidden />{store.phone}</a>}
      {store.telegram && (
        <a href={telegramUrl(store.telegram)} target="_blank" rel="noreferrer" className="font-medium text-info hover:underline">
          <Send className="mr-1 inline size-4" aria-hidden />{t('product.telegram')}
        </a>
      )}
    </div>
  )
}

function OfferRow({ offer, usdRate, rateDate, market }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const { store } = offer

  return (
    <Card as="li" padded={false} className={`min-w-0 p-4 ${offer.is_in_stock ? '' : 'opacity-60'}`}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:gap-6">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-semibold">
            {store.name}
            {store.is_verified && <Badge tone="success"><BadgeCheck className="size-3.5" aria-hidden />{t('product.verified')}</Badge>}
          </p>
          <p className="text-sm text-muted">{[store.district, store.address].filter(Boolean).join(', ')}</p>
          <p className="mt-1 text-xs break-words text-faint" title={offer.raw_name}>{offer.raw_name}</p>
          {offer.note && <p className="mt-1 text-sm text-muted">{offer.note}</p>}
          <p className="mt-1 text-sm">
            <span className={offer.is_in_stock ? 'text-success' : 'text-muted'}>
              {t(offer.is_in_stock ? 'product.inStock' : 'product.outOfStock')}
            </span>
            {' · '}{t(`condition.${offer.condition}`)}
            {' · '}<span className="text-muted">{t('product.updated', { date: formatDate(offer.updated_at) })}</span>
          </p>
        </div>
        <div className="shrink-0 md:text-right">
          <Price price={offer.price} currency={offer.currency} usdRate={usdRate} rateDate={rateDate} />
          {offer.is_in_stock && <div className="mt-1"><MarketLabel info={market} /></div>}
        </div>
        <div className="shrink-0 md:w-44 md:text-right">
          {open ? <Contacts store={store} /> : <Button className="w-full md:w-auto" onClick={() => setOpen(true)}>{t('product.contact')}</Button>}
        </div>
      </div>
      <Flags flags={offer.flags} className="mt-3 grid gap-1" />
    </Card>
  )
}

export default function ProductPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const [sort, setSort] = useState('recommended')
  const [product, setProduct] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/catalog/products/${id}`, { params: { sort } })
      .then((res) => { setProduct(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
  }, [id, sort, t])

  if (error) return <ErrorText>{error}</ErrorText>
  if (!product) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </div>
    )
  }
  const specs = product.specs.filter((s) => s.key !== 'brand') // the brand has its own line

  return (
    <section>
      <button onClick={() => navigate(-1)} className="inline-flex min-h-9 items-center gap-1 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />{t('product.back')}
      </button>
      <div className="mt-2 grid grid-cols-[minmax(0,1fr)] items-start gap-4 lg:grid-cols-2 lg:gap-6">
      <Card>
      <p className="text-sm break-words text-muted">
        {t(`categories.${product.category}`)}
        {product.mxik_code && <span> · {t('product.mxik')}: {product.mxik_code}</span>}
      </p>
      <h1 className="mt-1 text-h2 break-words md:text-h1">{product.name}</h1>
      {product.brand && <p className="mt-1 text-muted">{t('product.brand')}: {product.brand}</p>}
      {specs.length > 0 && (
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
          {specs.map((s) => (
            <div key={s.key} className="contents">
              <dt className="text-muted">{specLabel(s.key, product.category)}</dt>
              {/* Not written by the seller: inferred by a rule, the reason is in the hover hint */}
              <dd>
                {s.inferred ? (
                  <span title={t(`specs.inferred.${s.inferred}`)} className="cursor-help border-b border-dotted border-faint">
                    {formatSpec(s)}<sup className="text-faint">*</sup>
                  </span>
                ) : formatSpec(s)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {specs.some((s) => s.inferred) && <p className="mt-1 text-xs text-faint">{t('product.inferredNote')}</p>}
      {product.suspect?.length > 0 && (
        <p className="mt-3 rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-sm text-warning"
          title={product.suspect.map((s) => `${specLabel(s.key, product.category)}: ${formatSpec(s)}`).join(', ')}>
          {t('product.specsNeedCheck')}
        </p>
      )}

      </Card>
      <ProductMarket market={product.market} usdRate={product.usd_rate} />
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-h2">{t('product.offers', { count: product.offers.length })}</h2>
        <Tabs value={sort} onChange={setSort} tabs={SORTS.map((s) => ({ value: s, label: t(`product.sort.${s}`) }))} />
      </div>
      {sort === 'recommended' && <p className="mt-1 text-sm text-muted">{t('product.recommendedHint')}</p>}
      {product.usd_rate && (
        <p className="mt-1 text-sm text-muted">{t('price.rateNote', { date: formatDayMonth(product.usd_rate_date), rate: formatPrice(product.usd_rate, 'UZS') })}</p>
      )}
      <ul className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-3">
        {product.offers.map((o) => <OfferRow key={o.id} offer={o} usdRate={product.usd_rate} rateDate={product.usd_rate_date} market={product.market?.offers[o.id]} />)}
      </ul>
    </section>
  )
}
