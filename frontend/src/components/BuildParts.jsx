import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { partText } from '../services/builds'
import { CategoryIcon } from './CategoryIcon'

const LEVEL_TONE = {
  exact: 'bg-success-soft text-success',
  integrated: 'bg-success-soft text-success',
  specs: 'bg-info-soft text-info',
  none: 'bg-surface-2 text-muted',
}
const SLOT_ICON = { storage: 'ssd', other: 'other' }

export function LevelBadge({ level }) {
  const { t } = useTranslation()
  return <span className={`inline-flex shrink-0 rounded-sm px-2 py-0.5 text-xs font-medium ${LEVEL_TONE[level]}`}>{t(`builds.level.${level}`)}</span>
}

// The parts of a build by slots, each with its precision level: an exact model is a link to its card;
// "only specs" says what is known and that the maker is not; "not specified" shows the seller's words
export default function BuildParts({ parts, dictionary }) {
  const { t } = useTranslation()
  return (
    <ul className="divide-y divide-line">
      {parts.map((p, i) => (
        <li key={p.id ?? i} className="flex gap-3 py-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft/60 text-primary">
            <CategoryIcon category={SLOT_ICON[p.slot] || p.slot} className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
              {t(`builds.slot.${p.slot}`)}{p.quantity > 1 && <span className="font-semibold text-ink">× {p.quantity}</span>}
              <LevelBadge level={p.level} />
            </p>
            {p.level === 'exact' ? (
              <Link to={`/products/${p.product.id}`} className="mt-0.5 block font-medium break-words text-primary hover:underline">{p.product.name}</Link>
            ) : (
              <p className={`mt-0.5 break-words ${p.level === 'none' && !p.raw_text ? 'text-muted' : 'font-medium'}`}>{partText(p, dictionary)}</p>
            )}
            {p.level === 'specs' && !p.specs?.brand && <p className="text-xs text-muted">{t('builds.makerUnknown')}</p>}
            {p.level === 'specs' && p.raw_text && <p className="text-xs break-words text-faint">{t('builds.sellerText', { text: p.raw_text })}</p>}
          </div>
        </li>
      ))}
    </ul>
  )
}
