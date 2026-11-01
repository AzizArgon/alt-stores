import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import LineChart, { SERIES_COLORS } from './LineChart'
import { formatDayMonth, formatMonthYear, formatPrice, roundSum } from '../services/format'

export const PERIODS = ['week', 'month', 'quarter']
// Categories drawn on the index chart, each always in its own colour (colour follows the category)
const CHART_CATEGORIES = ['ram', 'ssd', 'gpu', 'cpu', 'motherboard', 'monitor', 'psu', 'case']

export function formatPct(value) {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toLocaleString('ru', { maximumFractionDigits: 1 })}%`
}

const PCT_COLOR = (v) => (v > 0.5 ? 'text-danger' : v < -0.5 ? 'text-success' : 'text-muted')

export function PctText({ value }) {
  return <span className={`font-medium ${PCT_COLOR(value)}`}>{formatPct(value)}</span>
}

// Small mark where numbers are computed with the invented demo stores; the hint explains it
export function DemoNote({ show }) {
  const { t } = useTranslation()
  if (!show) return null
  return (
    <span title={t('market.demoHint')} className="cursor-help whitespace-nowrap rounded border border-dashed border-line-strong px-1.5 py-0.5 text-xs font-normal text-muted">
      {t('market.demoNote')}
    </span>
  )
}

// "ниже рынка на 8%" / "по рынку" / "выше рынка на 12%"
export function MarketLabel({ info }) {
  const { t } = useTranslation()
  if (!info) return null
  const style = { below: 'bg-success-soft text-success', at: 'bg-surface-2 text-ink', above: 'bg-warning-soft text-warning' }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs ${style[info.label]}`} title={t('market.labelHint')}>
      {t(`market.label.${info.label}`, { pct: Math.abs(info.diff_pct) })}
    </span>
  )
}

// "за 3 месяца цена выросла на 5%"
export function ChangePhrase({ change }) {
  const { t } = useTranslation()
  if (!change) return <span className="text-muted">{t('market.notEnoughHistory')}</span>
  const period = change.days >= 80 ? t('market.period.quarter') : change.days >= 28 ? t('market.period.month') : t('market.days', { count: change.days })
  const key = Math.abs(change.pct) < 0.5 ? 'same' : change.pct > 0 ? 'up' : 'down'
  return <span>{t(`market.change.${key}`, { period, pct: formatPct(Math.abs(change.pct)).replace('+', '') })}</span>
}

// Product card: market price chart (median, in sums by today's rate), the change phrase, the old price list point
export function ProductMarket({ market, usdRate }) {
  const { t } = useTranslation()
  const info = market?.conditions?.new
  const archive = market?.archive
  const toSum = (usd) => (usdRate ? roundSum(usd * usdRate) : usd)
  const chart = useMemo(() => {
    if (!info || info.series.length < 2) return null
    const labels = [...(archive ? [formatMonthYear(archive.date)] : []), ...info.series.map((p) => formatDayMonth(p.date))]
    const pad = archive ? [null] : []
    const datasets = [{ label: t('market.marketPrice'), color: SERIES_COLORS[0], data: [...pad, ...info.series.map((p) => toSum(p.usd))] }]
    if (archive) {
      datasets.push({ label: t('market.archiveLabel', { store: archive.store, date: formatMonthYear(archive.date) }), color: SERIES_COLORS[1], points: 5,
        data: [toSum(archive.price_usd), ...info.series.map(() => null)] })
    }
    return { labels, datasets }
  }, [info, archive, usdRate, t]) // eslint-disable-line react-hooks/exhaustive-deps
  const formatValue = useMemo(() => (v) => formatPrice(v, usdRate ? 'UZS' : 'USD'), [usdRate])

  return (
    <div className="mt-6 max-w-3xl rounded-xl border border-line bg-surface shadow-card p-5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="flex items-center gap-2 text-h2">{t('market.productTitle')} <DemoNote show={info?.includes_demo} /></h2>
        {info?.market_usd != null && (
          <p className="text-sm text-muted">
            {t('market.marketNow', { stores: info.stores })}: <b>≈ {formatValue(toSum(info.market_usd))}</b>
          </p>
        )}
      </div>
      {info?.market_usd == null ? (
        <p className="mt-2 text-sm text-muted">{t('market.notEnoughStores')}</p>
      ) : (
        <>
          <p className="mt-1 text-sm"><ChangePhrase change={info.change} /></p>
          {chart && <div className="mt-3"><LineChart labels={chart.labels} datasets={chart.datasets} formatValue={formatValue} height={200} /></div>}
          <p className="mt-2 text-xs text-faint">{t('market.chartNote')}</p>
        </>
      )}
      {archive && (
        <p className="mt-2 text-sm text-muted">
          {t('market.archiveLine', { store: archive.store, date: formatMonthYear(archive.date) })}: {archive.price_uzs != null && <>{formatPrice(archive.price_uzs, 'UZS')} · </>}
          {formatPrice(archive.price_usd, 'USD')}
          {info?.market_usd != null && <> · {t('market.sinceArchive')} <PctText value={(info.market_usd / archive.price_usd - 1) * 100} /></>}
        </p>
      )}
    </div>
  )
}

// Category index: period switch, chart of the main categories, table of all of them
export function IndexSection({ indices, period, onPeriod, demo }) {
  const { t } = useTranslation()
  const chart = useMemo(() => {
    const cats = CHART_CATEGORIES.filter((c) => indices.series[c])
    if (!cats.length) return null
    const labels = indices.series[cats[0]].map((p) => formatDayMonth(p.date))
    const datasets = cats.map((c) => ({ label: t(`categories.${c}`), color: SERIES_COLORS[CHART_CATEGORIES.indexOf(c)],
      data: indices.series[c].map((p) => p.index) }))
    return { labels, datasets }
  }, [indices, t])
  const formatValue = useMemo(() => (v) => v.toLocaleString('ru', { maximumFractionDigits: 1 }), [])

  return (
    <section className="rounded-xl border border-line bg-surface shadow-card p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 text-h2">{t('market.indexTitle')} <DemoNote show={demo} /></h2>
        <div className="flex rounded-md border border-line-strong bg-surface p-0.5 text-sm">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => onPeriod(p)}
              className={`rounded px-3 py-1.5 ${period === p ? 'bg-primary text-white' : 'hover:bg-surface-2'}`}>
              {t(`market.periodShort.${p}`)}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-sm text-muted">{t('market.indexHint')}</p>
      {chart ? <div className="mt-4"><LineChart labels={chart.labels} datasets={chart.datasets} formatValue={formatValue} /></div>
        : <p className="mt-4 text-sm text-muted">{t('market.notEnoughData')}</p>}
      <table className="mt-6 w-full text-sm">
        <thead className="text-left text-muted">
          <tr>
            <th className="py-1 font-normal">{t('market.table.category')}</th>
            <th className="py-1 text-right font-normal">{t('market.table.products')}</th>
            {PERIODS.map((p) => <th key={p} className="py-1 text-right font-normal">{t(`market.periodShort.${p}`)}</th>)}
          </tr>
        </thead>
        <tbody>
          {indices.rows.map((r) => (
            <tr key={r.category} className="border-t border-line">
              <td className="py-1.5">{t(`categories.${r.category}`)}</td>
              <td className="py-1.5 text-right text-muted">{r.products}</td>
              {PERIODS.map((p) => <td key={p} className="py-1.5 text-right"><PctText value={r[p]} /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function ProductLink({ item }) {
  return <Link to={`/products/${item.id}`} className="hover:underline">{item.name}</Link>
}
