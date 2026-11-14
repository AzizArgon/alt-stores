import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDayMonth, formatPrice, roundSum, roundUsd } from '../services/format'

// Phase 16.2: the CBU rate is not a line on the page any more — only a tooltip of "≈" (hover, focus or a tap)
export function rateTip(t, usdRate, rateDate) {
  const rate = formatPrice(usdRate, 'UZS')
  return rateDate ? t('price.rateTip', { date: formatDayMonth(rateDate), rate }) : t('price.rateTipNoDate', { rate })
}

export function RateMark({ tip }) {
  const [open, setOpen] = useState(false)
  // The price is often inside a link (a tile): the tap shows the rate, it does not open the card
  const toggle = (e) => { e.preventDefault(); e.stopPropagation(); setOpen(!open) }
  return (
    <span className="group/rate relative inline-block">
      <button type="button" onClick={toggle} onBlur={() => setOpen(false)} aria-label={tip} title={tip}
        className="cursor-help rounded-sm font-normal text-muted underline decoration-dotted underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-primary">≈</button>
      <span role="tooltip"
        className={`pointer-events-none absolute bottom-full left-0 z-30 mb-1.5 w-max max-w-60 rounded-md bg-ink px-2 py-1 text-xs font-normal tracking-normal whitespace-normal text-white shadow-pop group-hover/rate:block ${open ? 'block' : 'hidden'}`}>
        {tip}
      </span>
      {' '}
    </span>
  )
}

// Main price is always in sum (payments in Uzbekistan are in the national currency), dollars below in grey.
// "≈" marks only the currency converted by the CBU rate; the seller's own one is exact.
export default function Price({ price, currency, usdRate, rateDate, prefix = '', size = 'text-xl' }) {
  const { t } = useTranslation()
  if (price == null) return <span className="text-faint">—</span>
  if (!usdRate) {
    // No CBU rate yet: show what the seller wrote, nothing to convert
    return <p className={`${size} font-bold tracking-tight`}>{prefix}{formatPrice(price, currency)}</p>
  }
  const tip = rateTip(t, usdRate, rateDate)
  const sum = currency === 'UZS' ? price : roundSum(price * usdRate)
  const usd = currency === 'USD' ? price : roundUsd(price / usdRate)
  return (
    <div>
      <p className={`${size} font-bold tracking-tight`}>
        {prefix && <span className="text-sm font-normal text-muted">{prefix}</span>}
        {currency === 'USD' && <RateMark tip={tip} />}{formatPrice(sum, 'UZS')}
      </p>
      <p className="text-sm text-muted">
        {currency === 'UZS' && <RateMark tip={tip} />}{formatPrice(usd, 'USD')}
      </p>
    </div>
  )
}
