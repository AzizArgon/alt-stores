import { Store, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { formatPrice, roundSum } from '../services/format'
import { specsLine } from '../services/specs'
import { ProductVisual } from './CategoryIcon'
import Price from './Price'

const FLAG_TONE = { warning: 'bg-warning-soft text-warning', danger: 'bg-danger-soft text-danger' }

// Catalog tile: picture place, name, key specs, the lowest price ("from", sums big, dollars grey), stores
// item.own: a tile of the store page (phase 12) - the store's own price, not "from", no store count
export default function ProductTile({ item, usdRate, rateDate, to, className = '' }) {
  const { t } = useTranslation()
  return (
    <Link to={to || `/products/${item.id}`}
      className={`group relative flex min-w-0 flex-col rounded-xl border border-line bg-surface p-3 shadow-card transition-shadow outline-none hover:shadow-hover focus-visible:ring-2 focus-visible:ring-primary md:p-4 ${className}`}>
      <ProductVisual category={item.category} image={item.image} alt={item.name} className="aspect-square w-full" />
      {item.flag_level && (
        <span title={t('catalog.flagHint')} aria-label={t('catalog.flagHint')}
          className={`absolute top-4 right-4 flex size-7 items-center justify-center rounded-full md:top-5 md:right-5 ${FLAG_TONE[item.flag_level]}`}>
          <TriangleAlert className="size-4" aria-hidden />
        </span>
      )}
      <span className="mt-3 text-xs text-muted">{t(`categories.${item.category}`)}</span>
      <span className="mt-0.5 line-clamp-2 text-sm font-semibold leading-snug break-words group-hover:text-primary md:text-base">{item.name}</span>
      {item.specs?.length > 0 && <span className="mt-1 line-clamp-2 text-xs break-words text-muted">{specsLine(item.specs.slice(0, 3))}</span>}
      <div className="mt-auto pt-3">
        <Price price={item.min_price} currency={item.min_currency} usdRate={usdRate} rateDate={rateDate}
          prefix={item.own ? '' : `${t('catalog.from')} `} size="text-base md:text-lg" />
        {item.own
          ? item.condition && item.condition !== 'new' && <span className="mt-1 block text-xs text-muted">{t(`condition.${item.condition}`)}</span>
          : (
            <span className="mt-1 flex items-center gap-1 text-xs text-muted">
              <Store className="size-3.5" aria-hidden />{t('catalog.stores', { count: item.offers })}
            </span>
          )}
        {item.used_from && (
          <span className="mt-0.5 block text-xs text-muted">
            {t('catalog.usedFrom', { price: item.used_from.price_uzs != null
              ? formatPrice(roundSum(item.used_from.price_uzs), 'UZS') : formatPrice(item.used_from.price, item.used_from.currency) })}
          </span>
        )}
      </div>
    </Link>
  )
}
