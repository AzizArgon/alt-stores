import { BadgeCheck, CircleCheck, MapPin, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import BuildParts from '../components/BuildParts'
import { PrecisionBadge } from '../components/BuildTile'
import { ProductVisual } from '../components/CategoryIcon'
import Flags from '../components/Flags'
import Price from '../components/Price'
import { Badge, Breadcrumbs, Button, Card, Skeleton } from '../components/ui'
import api, { errorKey } from '../services/api'
import { formatDate, formatPrice, roundSum } from '../services/format'
import { useSpecDictionary } from '../services/specs'
import { WriteButton } from '../components/Chat'
import { MapButtons, StoreName } from '../components/StoreWhere'
import { ReserveButton } from '../components/Reservation'
import { Contacts } from './ProductPage'

// "These parts separately in this store": a neutral line, no percent, no colour, not a warning
function StoreReference({ reference }) {
  const { t } = useTranslation()
  if (!reference) return null
  const price = reference.currency === 'UZS' ? formatPrice(roundSum(reference.price), 'UZS') : formatPrice(reference.price, reference.currency)
  return (
    <div className="mt-4 border-t border-line pt-3">
      <p className="text-sm">{t('builds.storeRef', { price })}</p>
      <p className="mt-0.5 text-xs text-muted">{t('builds.storeRefHint')}</p>
    </div>
  )
}

function Checks({ build }) {
  const { t } = useTranslation()
  const nothing = !build.flags.length && !build.compatibility.length
  return (
    <Card>
      <h2 className="text-h3">{t('builds.checks')}</h2>
      {nothing && <p className="mt-2 flex gap-1.5 text-sm text-success"><CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />{t('builds.noChecks')}</p>}
      {build.compatibility.length > 0 && (
        <div className="mt-3 rounded-md border border-warning-line bg-warning-soft p-3 text-sm text-warning">
          <p className="flex gap-1.5 font-semibold"><TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />{t('builds.compatTitle')}</p>
          <ul className="mt-1 grid gap-1 pl-6">
            {build.compatibility.map((c) => <li key={c.key}>{t(`builds.compat.${c.key}`, c.params)}</li>)}
          </ul>
          <p className="mt-1.5 pl-6 text-xs opacity-80">{t('builds.compatHint')}</p>
        </div>
      )}
      <Flags flags={build.flags} className="mt-3 grid gap-1.5" />
    </Card>
  )
}

export default function BuildPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [build, setBuild] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const dictionary = useSpecDictionary()

  useEffect(() => {
    setBuild(null)
    api.get(`/builds/${id}`)
      .then((res) => setBuild(res.data))
      .catch((err) => setError(err.response?.status === 404 ? t('builds.notFound') : t(errorKey(err))))
  }, [id, t])

  const crumbs = [{ to: '/', label: t('catalog.home') }, { to: '/builds', label: t('builds.title') }]
  if (error) return <section><Breadcrumbs items={crumbs} /><div className="mt-4"><ErrorText>{error}</ErrorText></div></section>
  if (!build) return <section className="grid gap-4"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-64" /></section>
  const { store } = build
  const place = [t(`cities.${store.city}`), store.district, store.address].filter(Boolean).join(', ')

  return (
    <section>
      <Breadcrumbs items={[...crumbs, { label: build.name }]} />
      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start lg:gap-6">
        <div className="grid min-w-0 gap-4">
          <div className="flex gap-4">
            <ProductVisual category="desktop" className="hidden size-24 sm:flex" />
            <div className="min-w-0">
              <p className="flex flex-wrap gap-1.5">
                <Badge tone="primary">{t(`builds.purpose.${build.purpose}`)}</Badge>
                <Badge>{t(`builds.condition.${build.condition}`)}</Badge>
              </p>
              <h1 className="mt-1.5 text-h2 break-words md:text-h1">{build.name}</h1>
              <p className="mt-1 text-sm text-muted">{t('builds.updated', { date: formatDate(build.updated_at) })}</p>
              {/* A phone sees the price at once; the store card with "Contact" is under the parts there */}
              <div className="mt-2 lg:hidden">
                <Price price={build.price} currency={build.currency} usdRate={build.usd_rate} rateDate={build.usd_rate_date} size="text-h2" />
              </div>
            </div>
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-h3">{t('builds.composition')}</h2>
              <PrecisionBadge precision={build.precision} long />
            </div>
            <BuildParts parts={build.components} dictionary={dictionary} />
            <StoreReference reference={build.store_reference} />
          </Card>

          <Checks build={build} />

          {build.description && (
            <Card>
              <h2 className="text-h3">{t('builds.description')}</h2>
              <p className="mt-2 text-sm break-words whitespace-pre-line">{build.description}</p>
            </Card>
          )}
        </div>

        <Card className="lg:sticky lg:top-20">
          <Price price={build.price} currency={build.currency} usdRate={build.usd_rate} rateDate={build.usd_rate_date} size="text-h1" />
          <div className="mt-4 border-t border-line pt-4">
            <p className="text-xs text-muted">{t('builds.store')}</p>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-h3">
              <StoreName store={store} />
              {store.is_verified && <Badge tone="success"><BadgeCheck className="size-3.5" aria-hidden />{t('product.verified')}</Badge>}
            </p>
            <p className="mt-0.5 flex gap-1 text-sm text-muted"><MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />{place}</p>
            {store.hours && <p className="mt-0.5 pl-5 text-sm text-muted">{store.hours}</p>}
            <MapButtons store={store} className="mt-2" />
          </div>
          <div className="mt-4 grid gap-2">
            <ReserveButton store={store} usdRate={build.usd_rate} className="w-full" item={{
              kind: 'build', id: build.id, title: build.name, condition: build.condition, price: build.price,
              currency: build.currency, inStock: build.is_in_stock, branches: build.branches }} />
            <WriteButton kind="build" id={build.id} store={store} className="w-full" />
            {open ? <Contacts store={store} />
              : <Button size="lg" className="w-full" onClick={() => setOpen(true)}>{t('product.contact')}</Button>}
          </div>
        </Card>
      </div>
    </section>
  )
}
