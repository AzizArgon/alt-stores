import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useOutletContext } from 'react-router-dom'
import { ArrowRight, CircleCheck, CircleSlash, Clock, ShieldAlert } from 'lucide-react'
import { DemoNote } from '../components/Market'
import { Button, Card, Skeleton } from '../components/ui'
import api from '../services/api'

// Each number opens "My goods" with the matching filter
const STATS = [
  { key: 'in_stock', icon: CircleCheck, tone: 'text-success', query: 'stock=in' },
  { key: 'out_of_stock', icon: CircleSlash, tone: 'text-muted', query: 'stock=out' },
  { key: 'flagged', icon: ShieldAlert, tone: 'text-warning', query: 'flagged=1' },
  { key: 'stale', icon: Clock, tone: 'text-faint', query: 'stale=1' },
]
const MARKET = [
  { key: 'below', tone: 'text-below' },
  { key: 'at', tone: 'text-at' },
  { key: 'above', tone: 'text-above' },
]

// "Overview": what is with the store's goods right now and where to go next
export default function CabinetOverview() {
  const { t } = useTranslation()
  const { store } = useOutletContext()
  const [data, setData] = useState(null)
  const [market, setMarket] = useState(null)

  useEffect(() => {
    api.get('/seller/overview').then((res) => setData(res.data)).catch(() => setData({}))
    api.get('/seller/analytics', { params: { period: 'quarter' } }).then((res) => setMarket(res.data)).catch(() => {})
  }, [])

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-h2 break-words md:text-h1">{store.name}</h1>
          <p className="mt-1 text-sm text-muted">
            {data?.last_upload
              ? t('cabinet.overview.lastUpload', { date: new Date(data.last_upload.created_at).toLocaleDateString('ru-RU') })
              : data && t('cabinet.overview.noUpload')}
          </p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <Button to="/seller/add?method=file" className="flex-1 sm:flex-none">{t('cabinet.overview.upload')}</Button>
          <Button to="/seller/add?method=catalog" variant="secondary" className="flex-1 sm:flex-none">{t('cabinet.overview.addOne')}</Button>
        </div>
      </div>

      {!data ? <Skeleton className="h-28 w-full rounded-xl" /> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {STATS.map(({ key, icon: Icon, tone, query }) => (
            <Link key={key} to={`/seller/goods?${query}`}
              className="rounded-xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-hover">
              <Icon className={`size-5 ${tone}`} aria-hidden />
              <p className="mt-2 text-h1 tabular-nums">{data[key] ?? 0}</p>
              <p className="text-sm text-muted">{t(`cabinet.overview.stat.${key}`)}</p>
            </Link>
          ))}
        </div>
      )}
      {data?.stale > 0 && <p className="-mt-3 text-xs text-muted">{t('cabinet.overview.staleHint')}</p>}

      <Card as="section">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex flex-wrap items-center gap-2 text-h3">{t('cabinet.overview.marketTitle')} <DemoNote show={market?.includes_demo} /></h2>
          <Link to="/seller/analytics" className="flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            {t('cabinet.overview.marketMore')}<ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
        <p className="mt-1 text-sm text-muted">{t('cabinet.overview.marketHint')}</p>
        {!market ? <Skeleton className="mt-4 h-16 w-full" /> : (
          <div className="mt-4 grid grid-cols-3 gap-3">
            {MARKET.map(({ key, tone }) => (
              <Link key={key} to={`/seller/goods?market=${key}`} className="rounded-lg bg-surface-2 p-3 hover:bg-line">
                <p className={`text-h2 tabular-nums ${tone}`}>{market.position.counts[key]}</p>
                <p className="text-xs text-muted md:text-sm">{t(`cabinet.overview.market.${key}`)}</p>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
