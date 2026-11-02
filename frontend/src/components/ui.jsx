// Basic building blocks of every page. All of them are shown on the /ui page (development only)
import { ChevronDown, ChevronLeft, ChevronRight, Eye, EyeOff, SearchX } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

const BUTTON_VARIANT = {
  primary: 'bg-primary text-white hover:bg-primary-hover',
  secondary: 'border border-line-strong bg-surface text-ink hover:bg-surface-2',
  text: 'text-primary hover:bg-primary-soft',
  danger: 'bg-danger text-white hover:bg-danger-hover',
}
const BUTTON_SIZE = {
  sm: 'min-h-9 px-3 text-sm',
  md: 'min-h-11 px-4 text-sm',
  lg: 'min-h-12 px-6 text-base',
}

// Button; with `to` it is a router link that looks the same
export function Button({ variant = 'primary', size = 'md', to, className = '', children, ...props }) {
  const style = `inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${BUTTON_VARIANT[variant]} ${BUTTON_SIZE[size]} ${className}`
  if (to) return <Link to={to} className={style} {...props}>{children}</Link>
  return <button type="button" className={style} {...props}>{children}</button>
}

export const inputClass = 'w-full min-h-11 rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-faint hover:border-faint focus:border-primary focus:ring-2 focus:ring-primary-soft disabled:bg-surface-2 disabled:text-faint'
const invalidClass = 'border-danger focus:border-danger focus:ring-danger-soft'

// Label above, hint or error below
export function FieldBox({ label, error, hint, id, children, className = '' }) {
  return (
    <div className={className}>
      {label && <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>}
      {children}
      {error && <p id={`${id}-error`} className="mt-1.5 text-sm text-danger">{error}</p>}
      {!error && hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  )
}

export function Input({ label, error, hint, className = '', ...props }) {
  const id = useId()
  return (
    <FieldBox label={label} error={error} hint={hint} id={id} className={className}>
      <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined}
        className={`${inputClass} ${error ? invalidClass : ''}`} {...props} />
    </FieldBox>
  )
}

// Password field with the show/hide eye
export function PasswordInput({ label, error, hint, className = '', ...props }) {
  const { t } = useTranslation()
  const id = useId()
  const [shown, setShown] = useState(false)
  const Icon = shown ? EyeOff : Eye
  return (
    <FieldBox label={label} error={error} hint={hint} id={id} className={className}>
      <div className="relative">
        <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined}
          className={`${inputClass} pr-11 ${error ? invalidClass : ''}`} {...props} type={shown ? 'text' : 'password'} />
        <button type="button" onClick={() => setShown(!shown)} aria-pressed={shown}
          aria-label={t(shown ? 'auth.hidePassword' : 'auth.showPassword')} title={t(shown ? 'auth.hidePassword' : 'auth.showPassword')}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-md text-muted outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-primary">
          <Icon className="size-5" aria-hidden />
        </button>
      </div>
    </FieldBox>
  )
}

export function Select({ label, error, hint, className = '', selectClassName = '', children, ...props }) {
  const id = useId()
  return (
    <FieldBox label={label} error={error} hint={hint} id={id} className={className}>
      <div className="relative">
        <select id={id} className={`${inputClass} appearance-none pr-9 ${error ? invalidClass : ''} ${selectClassName}`} {...props}>
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
      </div>
    </FieldBox>
  )
}

export function Checkbox({ label, className = '', ...props }) {
  return (
    <label className={`flex min-h-7 cursor-pointer items-center gap-2 text-sm ${className}`}>
      <input type="checkbox" className="size-4 shrink-0 cursor-pointer accent-primary" {...props} />
      <span className="min-w-0">{label}</span>
    </label>
  )
}

export function Switch({ checked, onChange, label, disabled }) {
  return (
    <label className={`inline-flex min-h-7 items-center gap-2 text-sm ${disabled ? 'opacity-50' : 'cursor-pointer'}`}>
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        className={`relative h-6 w-10 shrink-0 rounded-full outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${checked ? 'bg-primary' : 'bg-line-strong'}`}>
        <span className={`absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow-card transition-transform ${checked ? 'translate-x-4' : ''}`} />
      </button>
      {label}
    </label>
  )
}

export function Card({ as: Tag = 'div', padded = true, className = '', children, ...props }) {
  return <Tag className={`rounded-xl border border-line bg-surface shadow-card ${padded ? 'p-4 md:p-6' : ''} ${className}`} {...props}>{children}</Tag>
}

const BADGE_TONE = {
  neutral: 'bg-surface-2 text-muted',
  primary: 'bg-primary-soft text-primary',
  accent: 'bg-accent-soft text-above',
  success: 'bg-success-soft text-success',
  info: 'bg-info-soft text-info',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  below: 'bg-below-soft text-below',
  at: 'bg-at-soft text-at',
  above: 'bg-above-soft text-above',
}

export function Badge({ tone = 'neutral', className = '', children, ...props }) {
  return <span className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium ${BADGE_TONE[tone]} ${className}`} {...props}>{children}</span>
}

// Segmented switch: tabs = [{ value, label }]
export function Tabs({ tabs, value, onChange, label, className = '' }) {
  return (
    <div role="tablist" aria-label={label} className={`inline-flex max-w-full gap-0.5 overflow-x-auto rounded-md bg-surface-2 p-1 ${className}`}>
      {tabs.map((tab) => (
        <button key={tab.value} type="button" role="tab" aria-selected={value === tab.value} onClick={() => onChange(tab.value)}
          className={`min-h-9 shrink-0 rounded-sm px-3 text-sm font-medium whitespace-nowrap outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
            value === tab.value ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`}>
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-surface-2 ${className}`} />
}

// A grid of grey cards while the data is on its way
export function SkeletonCards({ count = 6, className = 'grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4' }) {
  return (
    <div className={className}>
      {Array.from({ length: count }, (_, i) => (
        <Card key={i} padded={false} className="p-3 md:p-4">
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-3/4" />
          <Skeleton className="mt-6 h-6 w-2/3" />
        </Card>
      ))}
    </div>
  )
}

export function EmptyState({ icon: Icon = SearchX, title, hint, children }) {
  return (
    <div className="flex flex-col items-center px-4 py-12 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-surface-2 text-muted"><Icon className="size-7" aria-hidden /></span>
      <p className="mt-4 text-h3">{title}</p>
      {hint && <p className="mt-1 max-w-md text-sm text-muted">{hint}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}

// "Главная › Процессоры": items = [{ to, label }], the last one is the current page (no link)
export function Breadcrumbs({ items, className = '' }) {
  return (
    <nav aria-label="breadcrumbs" className={`text-sm text-muted ${className}`}>
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, i) => (
          <li key={item.label} className="flex min-w-0 items-center gap-1">
            {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-faint" aria-hidden />}
            {item.to && i < items.length - 1
              ? <Link to={item.to} className="hover:text-primary hover:underline">{item.label}</Link>
              : <span aria-current="page" className="truncate text-ink">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  )
}

// The pages around the current one, with "…" over the gaps: 1 … 4 5 6 … 20
function pageList(page, pages) {
  const near = [...new Set([1, page - 1, page, page + 1, pages])].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b)
  return near.flatMap((p, i) => (i > 0 && p - near[i - 1] > 1 ? [`gap${p}`, p] : [p]))
}

export function Pagination({ page, pages, onChange, className = '' }) {
  const { t } = useTranslation()
  if (pages <= 1) return null
  const arrow = 'flex size-10 shrink-0 items-center justify-center rounded-md text-ink outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-40'
  return (
    <nav aria-label={t('catalog.pagination')} className={`flex items-center justify-center gap-0.5 md:gap-1 ${className}`}>
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label={t('catalog.prev')} className={arrow}>
        <ChevronLeft className="size-5" aria-hidden />
      </button>
      {pageList(page, pages).map((p) => (typeof p === 'string'
        ? <span key={p} className="w-5 text-center text-muted md:w-8">…</span>
        : (
          <button key={p} type="button" onClick={() => onChange(p)} aria-current={p === page ? 'page' : undefined}
            className={`h-10 min-w-9 rounded-md px-2 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-primary md:min-w-10 ${
              p === page ? 'bg-primary text-white' : 'text-ink hover:bg-surface-2'}`}>
            {p}
          </button>
        )))}
      <button type="button" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label={t('catalog.next')} className={arrow}>
        <ChevronRight className="size-5" aria-hidden />
      </button>
    </nav>
  )
}
