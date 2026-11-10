import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, ChevronDown, Phone, TriangleAlert, X } from 'lucide-react'
import { formatDate } from '../services/format'
import StoreWhere from './StoreWhere'

// A branch as a store-like object for StoreWhere / MapButtons (city, landmark as "district", address, hours, map)
const asPlace = (b) => ({ ...b, kind: 'shop' })

function BranchRow({ branch, tracked, route = false }) {
  const { t } = useTranslation()
  const Mark = branch.in_stock ? Check : X
  return (
    <li className="min-w-0 py-2.5">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        {tracked && (
          <span className={`inline-flex items-center gap-1 font-medium ${branch.in_stock ? 'text-success' : 'text-muted'}`}>
            <Mark className="size-4" aria-hidden />{t(branch.in_stock ? 'stock.buyer.yes' : 'stock.buyer.no')}
          </span>
        )}
        <span className="min-w-0 break-words font-medium">{branch.name || t(`cities.${branch.city}`)}</span>
        {branch.is_main && <span className="text-xs text-faint">{t('branches.main')}</span>}
      </p>
      <StoreWhere store={asPlace(branch)} route={route} className="mt-1" />
      {branch.phone && (
        <p className="mt-1 flex gap-1.5 text-sm text-muted"><Phone className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />
          <a href={`tel:${branch.phone.replace(/[^\d+]/g, '')}`} className="hover:text-primary">{branch.phone}</a></p>
      )}
      {tracked && branch.updated_at && (
        <p className={`mt-1 text-xs ${branch.stale ? 'text-warning' : 'text-faint'}`}>
          {branch.stale && <TriangleAlert className="mr-1 inline size-3.5 align-[-2px]" aria-hidden />}
          {t(branch.stale ? 'stock.buyer.stale' : 'stock.buyer.updated', { date: formatDate(branch.updated_at) })}
        </p>
      )}
    </li>
  )
}

// The product card: "Есть в 2 из 3 филиалов" (in the chosen city, else everywhere) and the list ✓ / ✗ on a click.
// The buyer never sees a quantity. Not tracked by branch: "наличие в филиале уточняйте у магазина"
export function BranchAvailability({ stock, city }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  if (!stock?.branches?.length) return null
  const many = stock.branches.length > 1
  if (!stock.tracked && !many) return null
  const where = city && city !== 'all' && stock.branches.some((b) => b.city === city) ? t(`cities.${city}`) : null
  const summary = stock.tracked
    ? t(where ? 'stock.buyer.inCity' : 'stock.buyer.summary', { available: stock.available, total: stock.total, city: where, count: stock.total })
    : t('stock.buyer.notTracked')
  return (
    <div className="mt-2 min-w-0 rounded-lg border border-line">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm">
        <span className={`min-w-0 ${stock.tracked && stock.available > 0 ? 'font-medium text-success' : 'text-muted'}`}>
          {summary}
          {stock.tracked && stock.stale && <span className="ml-1 text-warning">· {t('stock.buyer.staleShort')}</span>}
        </span>
        <ChevronDown className={`size-4 shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open && (
        <ul className="divide-y divide-line border-t border-line px-3" data-testid="branch-list">
          {stock.branches.map((b) => <BranchRow key={b.id} branch={b} tracked={stock.tracked} />)}
        </ul>
      )}
    </div>
  )
}

// The store page: every branch by city, with address, hours, phone, the map and the route
export function BranchesByCity({ branches, city }) {
  const { t } = useTranslation()
  if (!branches?.length) return null
  const cities = [...new Set(branches.map((b) => b.city))].sort((a, b) => (a === city ? -1 : b === city ? 1 : 0))
  return (
    <div className="grid gap-4">
      {cities.map((c) => (
        <section key={c} className="min-w-0">
          <h3 className="text-h3">{t(`cities.${c}`)} <span className="text-sm font-normal text-muted">· {t('stock.buyer.branchCount', { count: branches.filter((b) => b.city === c).length })}</span></h3>
          <ul className="mt-1 grid gap-x-6 divide-y divide-line md:grid-cols-2 md:divide-y-0">
            {branches.filter((b) => b.city === c).map((b) => <BranchRow key={b.id} branch={b} tracked={false} route />)}
          </ul>
        </section>
      ))}
    </div>
  )
}
