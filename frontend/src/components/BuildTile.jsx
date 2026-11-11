import { CircleCheck, MapPin, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { allPrecise, partText } from '../services/builds'
import { ProductVisual } from './CategoryIcon'
import Price from './Price'

const KEY_SLOTS = ['cpu', 'gpu', 'ram', 'storage']

// "Точно: 4 из 6" — how many parts the store named by an exact model (green only when all of them)
export function PrecisionBadge({ precision, long = false, className = '' }) {
  const { t } = useTranslation()
  const full = allPrecise(precision)
  return (
    <span title={t('builds.precisionHint')}
      className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium ${full ? 'bg-success-soft text-success' : 'bg-surface-2 text-muted'} ${className}`}>
      {full && <CircleCheck className="size-3.5" aria-hidden />}
      {t(long ? 'builds.precisionLong' : 'builds.precision', precision)}
    </span>
  )
}

// A ready PC in the list: no market label or rating — builds of different stores are not compared
export default function BuildTile({ item, dictionary, usdRate, rateDate, className = '' }) {
  const { t } = useTranslation()
  const parts = KEY_SLOTS.map((slot) => [slot, item.key_parts.filter((p) => p.slot === slot)]).filter(([, list]) => list.length)
  return (
    <Link to={`/builds/${item.id}`}
      className={`group relative flex min-w-0 flex-col rounded-xl border border-line bg-surface p-3 shadow-card transition-shadow outline-none hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary md:p-4 ${className}`}>
      <ProductVisual category="desktop" image={item.image} alt={item.name} className="aspect-square w-full" />
      {item.warnings > 0 && (
        <span title={t('builds.warnings')} aria-label={t('builds.warnings')}
          className="absolute top-4 right-4 flex size-7 items-center justify-center rounded-full bg-warning-soft text-warning md:top-5 md:right-5">
          <TriangleAlert className="size-4" aria-hidden />
        </span>
      )}
      <span className="mt-3 text-xs text-muted">
        {t(`builds.purpose.${item.purpose}`)}{item.condition === 'used' && ` · ${t('builds.condition.used')}`}
      </span>
      <span className="mt-0.5 line-clamp-2 text-sm font-semibold leading-snug break-words group-hover:text-primary md:text-base">{item.name}</span>
      <ul className="mt-1.5 grid gap-0.5 text-xs text-muted">
        {parts.map(([slot, list]) => (
          <li key={slot} className="line-clamp-1 break-all">
            <span className="text-faint">{t(`builds.slot.${slot}`)}: </span>
            {list.map((p) => `${p.quantity > 1 ? `${p.quantity}× ` : ''}${partText(p, dictionary)}`).join(', ')}
          </li>
        ))}
      </ul>
      <PrecisionBadge precision={item.precision} className="mt-2 self-start" />
      <div className="mt-auto pt-3">
        <Price price={item.price} currency={item.currency} usdRate={usdRate} rateDate={rateDate} size="text-base md:text-lg" />
        <span className="mt-1 flex min-w-0 items-center gap-1 text-xs text-muted">
          <MapPin className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{item.store.name}, {t(`cities.${item.store.city}`)}</span>
        </span>
      </div>
    </Link>
  )
}
