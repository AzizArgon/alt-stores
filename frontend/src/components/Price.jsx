import { useTranslation } from 'react-i18next'
import { formatDayMonth, formatPrice, roundSum, roundUsd } from '../services/format'

// Main price is always in sum (payments in Uzbekistan are in the national currency), dollars below in grey.
// "≈" marks only the currency converted by the CBU rate; the seller's own one is exact.
export default function Price({ price, currency, usdRate, rateDate, prefix = '', size = 'text-xl' }) {
  const { t } = useTranslation()
  if (price == null) return <span className="text-faint">—</span>
  const hint = rateDate ? t('price.rateHint', { date: formatDayMonth(rateDate) }) : undefined
  if (!usdRate) {
    // No CBU rate yet: show what the seller wrote, nothing to convert
    return <p className={`${size} font-bold tracking-tight`}>{prefix}{formatPrice(price, currency)}</p>
  }
  const sum = currency === 'UZS' ? price : roundSum(price * usdRate)
  const usd = currency === 'USD' ? price : roundUsd(price / usdRate)
  return (
    <div>
      <p className={`${size} font-bold tracking-tight`} title={currency === 'USD' ? hint : undefined}>
        {prefix && <span className="text-sm font-normal text-muted">{prefix}</span>}
        {currency === 'USD' && <span className="font-normal text-muted">≈ </span>}{formatPrice(sum, 'UZS')}
      </p>
      <p className="text-sm text-muted" title={currency === 'UZS' ? hint : undefined}>
        {currency === 'UZS' && '≈ '}{formatPrice(usd, 'USD')}
      </p>
    </div>
  )
}
