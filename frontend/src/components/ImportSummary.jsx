import { ChevronRight, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card } from './ui'
import { formatPrice } from '../services/format'

export const IMPORT_MODES = ['full', 'append']
const GROUPS = ['price_up', 'price_down', 'new', 'out_of_stock', 'back_in_stock']
const GROUP_STYLE = {
  price_up: 'text-danger', price_down: 'text-success', new: 'text-primary', out_of_stock: 'text-warning', back_in_stock: 'text-success',
}
const LIST_LIMIT = 200

// "Full price list" or "addition": radio cards with a plain hint under each; nothing is chosen by default
export function ModeChoice({ mode, onChange, name = 'mode' }) {
  const { t } = useTranslation()
  return (
    <fieldset className="mt-4">
      <legend className="text-sm text-muted">{t('upload.mode')}</legend>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        {IMPORT_MODES.map((m) => (
          <label key={m} className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors ${
            mode === m ? 'border-primary bg-primary-soft' : 'border-line hover:border-primary'}`}>
            <input type="radio" name={name} className="mt-0.5 size-4 shrink-0 accent-primary" checked={mode === m}
              onChange={() => onChange(m)} />
            <span>
              <span className="block font-medium">{t(`upload.modes.${m}`)}</span>
              <span className="mt-0.5 block text-xs text-muted">{t(`upload.modeHints.${m}`)}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

const money = (price, currency) => (price == null ? '—' : formatPrice(price, currency))

function GroupItem({ item }) {
  const hasOld = item.old_price !== undefined
  return (
    <li className="flex flex-col gap-x-3 py-1.5 sm:flex-row sm:justify-between">
      <span className="min-w-0 break-words">{item.name}
        {item.raw_name !== item.name && <span className="block text-xs text-faint">{item.raw_name}</span>}
      </span>
      <span className="shrink-0 tabular-nums text-muted">
        {hasOld && <>{money(item.old_price, item.old_currency)} → </>}
        <span className="text-ink">{money(item.price, item.currency)}</span>
      </span>
    </li>
  )
}

// The groups of a summary, each opens into a list (old price -> new price): "what will change" and "what will come back"
function GroupList({ summary, groups, styles, prefix, always }) {
  const { t } = useTranslation()
  const count = (g) => summary[g].length
  return groups.map((g) => (g === always || count(g) > 0) && (
    <details key={g} className="group py-1" open={false}>
      <summary className={`flex cursor-pointer list-none items-center gap-2 py-1.5 text-sm ${count(g) ? '' : 'pointer-events-none'}`}>
        <ChevronRight className={`size-4 shrink-0 text-faint transition-transform group-open:rotate-90 ${count(g) ? '' : 'invisible'}`} aria-hidden />
        <span className={`font-semibold tabular-nums ${count(g) ? styles[g] : 'text-faint'}`}>{count(g)}</span>
        <span>{t(`${prefix}.${g}`, { count: count(g) })}</span>
      </summary>
      <ul className="mb-2 ml-6 max-h-80 divide-y divide-line overflow-y-auto text-sm">
        {summary[g].slice(0, LIST_LIMIT).map((item, i) => <GroupItem key={`${item.raw_name}-${i}`} item={item} />)}
        {count(g) > LIST_LIMIT && <li className="py-1.5 text-muted">{t('importSummary.more', { count: count(g) - LIST_LIMIT })}</li>}
      </ul>
    </details>
  ))
}

const UNDO_GROUPS = ['prices', 'back_in_stock', 'out_of_stock', 'removed_new', 'kept_new', 'conflicts']
const UNDO_STYLE = {
  prices: 'text-primary', back_in_stock: 'text-success', out_of_stock: 'text-warning', removed_new: 'text-danger',
  kept_new: 'text-warning', conflicts: 'text-muted',
}

// "What will come back" before undoing an upload (phase 12): the same look as "what will change"
export function UndoSummary({ summary }) {
  const { t } = useTranslation()
  const nothing = UNDO_GROUPS.every((g) => summary[g].length === 0)
  return (
    <div>
      <p className="text-sm text-muted">{t('undo.intro')}</p>
      <div className="mt-2 divide-y divide-line">
        {nothing
          ? <p className="py-2 text-sm text-muted">{t('undo.nothing')}</p>
          : <GroupList summary={summary} groups={UNDO_GROUPS} styles={UNDO_STYLE} prefix="undo.group" />}
      </div>
      {summary.conflicts.length > 0 && <p className="mt-2 text-xs text-muted">{t('undo.conflictsHint')}</p>}
    </div>
  )
}

// "What will change": the groups of the summary, each opens into a list (old price -> new price)
export default function ImportSummary({ summary, loading }) {
  const { t } = useTranslation()
  if (!summary) return null
  const count = (g) => summary[g].length
  return (
    <Card className={loading ? 'opacity-60' : ''}>
      <h2 className="text-h3">{t('importSummary.title')}</h2>
      <p className="mt-1 text-sm text-muted">{t(`importSummary.modeLine.${summary.mode}`)}</p>
      {summary.large_drop && (
        <div role="alert" className="mt-3 flex gap-2 rounded-lg border border-danger-line bg-danger-soft p-3 text-sm text-danger">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
          <span>
            <span className="block font-semibold">{t('importSummary.largeDropTitle')}</span>
            {t('importSummary.largeDrop', { count: count('out_of_stock'), total: summary.on_sale })}
          </span>
        </div>
      )}
      <div className="mt-3 divide-y divide-line">
        <GroupList summary={summary} groups={GROUPS} styles={GROUP_STYLE} prefix="importSummary.group" always="out_of_stock" />
        <p className="flex items-center gap-2 py-2.5 pl-6 text-sm">
          <span className="font-semibold tabular-nums text-faint">{summary.unchanged}</span>
          {t('importSummary.unchanged', { count: summary.unchanged })}
        </p>
      </div>
    </Card>
  )
}
