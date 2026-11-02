import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ErrorText } from '../components/AuthForm'
import { Card, Skeleton } from '../components/ui'
import { DemoNote, IndexSection, MarketLabel, ProductLink } from '../components/Market'
import api, { errorKey } from '../services/api'
import { formatPrice, roundSum } from '../services/format'

const COUNT_STYLE = { below: 'text-success', at: 'text-ink', above: 'text-warning' }

export default function SellerAnalyticsPage() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState('quarter')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/seller/analytics', { params: { period } })
      .then((res) => { setData(res.data); setError('') })
      .catch((err) => setError(t(errorKey(err))))
  }, [period, t])

  if (error) return <ErrorText>{error}</ErrorText>
  if (!data) return <div className="grid gap-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-96 w-full rounded-xl" /></div>
  const sum = (usd) => (data.usd_rate ? `≈ ${formatPrice(roundSum(usd * data.usd_rate), 'UZS')}` : formatPrice(usd, 'USD'))
  const { counts, gaps, no_data: noData } = data.position

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div>
        <h1 className="text-h2 md:text-h1">{t('market.analyticsTitle')}</h1>
        <p className="mt-1 text-muted">{t('market.analyticsHint')}</p>
      </div>

      <Card as="section">
        <h2 className="flex flex-wrap items-center gap-2 text-h2">{t('market.positionTitle')} <DemoNote show={data.includes_demo} /></h2>
        <p className="mt-1 text-sm text-muted">{t('market.positionHint')}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {['below', 'at', 'above'].map((k) => (
            <div key={k} className="rounded-lg bg-surface-2 p-4">
              <p className={`text-h1 ${COUNT_STYLE[k]}`}>{counts[k]}</p>
              <p className="text-sm text-muted">{t(`market.counts.${k}`)}</p>
            </div>
          ))}
          <div className="rounded-lg bg-surface-2 p-4">
            <p className="text-h1 text-faint">{noData}</p>
            <p className="text-sm text-muted">{t('market.counts.noData')}</p>
          </div>
        </div>
        <h3 className="mt-6 font-medium">{t('market.gapsTitle')}</h3>
        <table className="table-cards mt-2 w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="py-1 font-normal">{t('market.table.product')}</th>
              <th className="py-1 text-right font-normal">{t('market.table.yourPrice')}</th>
              <th className="py-1 text-right font-normal">{t('market.table.market')}</th>
              <th className="py-1 text-right font-normal">{t('market.table.stores')}</th>
              <th className="py-1 text-right font-normal">{t('market.table.diff')}</th>
            </tr>
          </thead>
          <tbody>
            {gaps.map((g) => (
              <tr key={`${g.id}-${g.condition}`} className="border-t border-line">
                <td className="py-1.5 pr-4"><ProductLink item={g} />{g.condition !== 'new' && <span className="text-muted"> · {t(`condition.${g.condition}`)}</span>}</td>
                <td data-label={t('market.table.yourPrice')} className="py-1.5 text-right whitespace-nowrap">{sum(g.price_usd)}</td>
                <td data-label={t('market.table.market')} className="py-1.5 text-right whitespace-nowrap">{sum(g.market_usd)}</td>
                <td data-label={t('market.table.stores')} className="py-1.5 text-right text-muted">{g.stores}</td>
                <td data-label={t('market.table.diff')} className="py-1.5 text-right whitespace-nowrap"><MarketLabel info={g} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card as="section">
        <h2 className="text-h2">{t('market.missingTitle')}</h2>
        <p className="mt-1 text-sm text-muted">{t('market.missingHint')}</p>
        {data.missing.length === 0 ? <p className="mt-3 text-sm text-muted">{t('market.missingNone')}</p> : (
          <ol className="mt-3 grid gap-1.5 text-sm">
            {data.missing.map((m, i) => (
              <li key={m.id} className="flex flex-col justify-between gap-x-4 border-t border-line pt-1.5 sm:flex-row">
                <span><span className="mr-2 text-faint">{i + 1}.</span><ProductLink item={m} /> <span className="text-muted">· {t(`categories.${m.category}`)}</span></span>
                <span className="whitespace-nowrap text-muted">{t('market.storesCount', { count: m.stores })} · {sum(m.market_usd)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <IndexSection indices={data.indices} period={period} onPeriod={setPeriod} demo={data.includes_demo} />
    </div>
  )
}
