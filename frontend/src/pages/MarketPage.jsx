import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ErrorText } from '../components/AuthForm'
import { MapPin } from 'lucide-react'
import { Badge, Breadcrumbs, Card, Skeleton } from '../components/ui'
import { DemoNote, IndexSection, PctText, ProductLink } from '../components/Market'
import api, { errorKey } from '../services/api'
import { formatMonthYear, formatPrice, roundSum } from '../services/format'

function Movers({ title, items, sum, demo }) {
  const { t } = useTranslation()
  return (
    <Card as="section" className="min-w-0">
      <h2 className="flex flex-wrap items-center gap-2 text-h2">{title} <DemoNote show={demo} /></h2>
      {items.length === 0 ? <p className="mt-3 text-sm text-muted">{t('market.notEnoughData')}</p> : (
        <ul className="mt-3 grid gap-1.5 text-sm">
          {items.map((m) => (
            <li key={m.id} className="flex flex-col justify-between gap-x-4 border-t border-line pt-1.5 sm:flex-row">
              <span className="min-w-0"><ProductLink item={m} /></span>
              <span className="whitespace-nowrap text-muted">{sum(m.from_usd)} → {sum(m.to_usd)} <PctText value={m.pct} /></span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function MarketPage() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState('quarter')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/market/overview', { params: { period } })
      .then((res) => { setData(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
  }, [period, t])

  if (error) return <ErrorText>{error}</ErrorText>
  if (!data) return <div className="grid gap-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-96 w-full rounded-xl" /></div>
  const then = data.archive[0] ? formatMonthYear(data.archive[0].archive.date) : ''
  const sum = (usd) => (data.usd_rate ? `≈ ${formatPrice(roundSum(usd * data.usd_rate), 'UZS')}` : formatPrice(usd, 'USD'))

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div>
        <Breadcrumbs items={[{ to: '/', label: t('catalog.home') }, { label: t('market.pageTitle') }]} />
        <h1 className="mt-2 flex flex-wrap items-center gap-3 text-h2 md:text-h1">
          {t('market.pageTitle')} <Badge tone="primary" title={t('market.scopeHint')}><MapPin className="size-3.5" aria-hidden />{t('market.scope')}</Badge>
        </h1>
        <p className="mt-1 max-w-3xl text-muted">{t('market.pageHint')} {t('market.scopeHint')}</p>
      </div>
      <IndexSection indices={data.indices} period={period} onPeriod={setPeriod} demo={data.includes_demo} />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
        <Movers title={t('market.moversUp')} items={data.movers.up} sum={sum} demo={data.includes_demo} />
        <Movers title={t('market.moversDown')} items={data.movers.down} sum={sum} demo={data.includes_demo} />
      </div>
      <Card as="section">
        <h2 className="flex flex-wrap items-center gap-2 text-h2">{t('market.archiveTitle', { date: then })} <DemoNote show={data.includes_demo} /></h2>
        <p className="mt-1 text-sm text-muted">{t('market.archiveHint', { date: then })}</p>
        <table className="table-cards mt-4 w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="py-1 font-normal">{t('market.table.product')}</th>
              <th className="py-1 text-right font-normal">{then}</th>
              <th className="py-1 text-right font-normal">{t('market.table.now')}</th>
              <th className="py-1 text-right font-normal">{t('market.table.change')}</th>
            </tr>
          </thead>
          <tbody>
            {data.archive.map((a) => (
              <tr key={a.id} className="border-t border-line">
                <td className="py-1.5 pr-4"><ProductLink item={a} /></td>
                <td data-label={then} className="py-1.5 text-right whitespace-nowrap">
                  <span>{a.archive.price_uzs != null ? formatPrice(a.archive.price_uzs, 'UZS') : ''}
                  <span className="block text-xs text-muted">{formatPrice(a.archive.price_usd, 'USD')}</span></span>
                </td>
                <td data-label={t('market.table.now')} className="py-1.5 text-right whitespace-nowrap">
                  <span>{sum(a.market_usd)}
                  <span className="block text-xs text-muted">{formatPrice(a.market_usd, 'USD')} · {t('market.storesCount', { count: a.stores })}</span></span>
                </td>
                <td data-label={t('market.table.change')} className="py-1.5 text-right"><PctText value={a.change_pct} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-faint">{t('market.archiveNote', { date: then })}</p>
      </Card>
    </div>
  )
}
