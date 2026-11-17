// Basic building blocks of every page. All of them are shown on the /ui page (development only)
import { ChevronDown, ChevronLeft, ChevronRight, Eye, EyeOff, SearchX } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
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
export function Button({ variant = 'primary', size = 'md', to, href, className = '', children, ...props }) {
  const style = `inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${BUTTON_VARIANT[variant]} ${BUTTON_SIZE[size]} ${className}`
  if (to) return <Link to={to} className={style} {...props}>{children}</Link>
  if (href) return <a href={href} className={style} {...props}>{children}</a>
  return <button type="button" className={style} {...props}>{children}</button>
}

// A link that may lead to the other interface (config/sites.js): in-app on the same site, a plain link otherwise
export function SiteLink({ url, ...props }) {
  return /^https?:\/\//.test(url) ? <a href={url} {...props} /> : <Link to={url} {...props} />
}

// Phase 17.3: in the cabinet and the admin only tables and lists take the whole width; a search field is 320–384 px
export const SEARCH_WIDTH = 'w-full sm:max-w-sm lg:w-96 lg:shrink-0'
// …and a row of filters (selects) is as wide as about four of them
export const FILTERS_WIDTH = 'max-w-5xl'
// Phase 17.4: the "zebra" of every table and list of the cabinet and the admin (colours — index.css .zebra-*).
// i — the row's place from 0: the 1st, 3rd… rows are white, the 2nd, 4th… light grey; a ticked row is light blue.
// Cells fixed on the left take the row's colour with ZEBRA_CELL; the header row of a table — ZEBRA_HEAD
export function zebra(i, selected = false) {
  return `zebra-row ${i % 2 ? 'zebra-even' : 'zebra-odd'}${selected ? ' zebra-selected' : ''}`
}
export const ZEBRA_CELL = 'zebra-cell'
export const ZEBRA_HEAD = 'zebra-head'

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
// Phase 17.3: a row of tabs never shows a scrollbar. A computer (768 px and wider): every tab in one row; the ones that
// do not fit go into "Ещё ˅" (the chosen one hidden there gives its name to that button). A phone: the row moves by a
// finger, the scrollbar hidden, the right edge fades while there is more to the right.
export const TABS_WIDE = '(min-width: 768px)'
export function Tabs({ tabs, value, onChange, label, className = '' }) {
  const { t } = useTranslation()
  const wide = useMedia(TABS_WIDE)
  const box = useRef(null)
  const ruler = useRef(null)
  const row = useRef(null)
  const [fit, setFit] = useState(tabs.length)
  const [open, setOpen] = useState(false)
  const fade = useEdgeFade(row, !wide)
  const names = tabs.map((x) => x.label).join('|')

  useLayoutEffect(() => {
    if (!wide) { setFit(tabs.length); return undefined }
    const measure = () => {
      const el = box.current
      const r = ruler.current
      if (!el || !r) return
      setFit(tabsThatFit([...r.children].map((c) => c.offsetWidth), el.clientWidth, tabs.findIndex((x) => x.value === value)))
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [wide, names, value]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => { if (e.type === 'keydown' ? e.key === 'Escape' : !box.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close) }
  }, [open])

  const shown = wide ? tabs.slice(0, fit) : tabs
  const rest = wide ? tabs.slice(fit) : []
  const hiddenActive = rest.find((x) => x.value === value)
  const tabClass = (on) => `min-h-9 shrink-0 rounded-sm px-2.5 text-sm font-medium whitespace-nowrap outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
    on ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`
  // className goes on a wrapper: "hidden sm:block" must not fight the tablist's own inline-flex
  return (
    <div ref={box} className={`relative min-w-0 ${className}`}>
      {/* The widths of every tab (and of "Ещё"), unseen: what fits is counted from them */}
      {wide && (
        <div ref={ruler} aria-hidden className="pointer-events-none invisible absolute top-0 left-0 flex h-0 gap-0.5 overflow-hidden whitespace-nowrap">
          {tabs.map((x) => <span key={x.value} className={tabClass(false)}>{x.label}</span>)}
          <span className={`${tabClass(false)} inline-flex items-center gap-1`}>{t('ui.more')}<ChevronDown className="size-4" /></span>
        </div>
      )}
      <div className="relative inline-flex max-w-full">
        <div ref={row} role="tablist" aria-label={label} data-testid="tabs-row"
          className={`no-scrollbar inline-flex max-w-full gap-0.5 overflow-x-auto overscroll-x-contain rounded-md bg-surface-2 p-1 ${fade ? 'fade-edge-r' : ''}`}>
          {shown.map((tab) => (
            <button key={tab.value} type="button" role="tab" aria-selected={value === tab.value} onClick={() => onChange(tab.value)} className={tabClass(value === tab.value)}>
              {tab.label}
            </button>
          ))}
          {rest.length > 0 && (
            <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} data-testid="tabs-more"
              className={`${tabClass(Boolean(hiddenActive))} inline-flex items-center gap-1`}>
              {hiddenActive ? hiddenActive.label : t('ui.more')}<ChevronDown className="size-4" aria-hidden />
            </button>
          )}
        </div>
        {open && rest.length > 0 && (
          <div role="menu" className="absolute top-full right-0 z-20 mt-1 grid min-w-44 rounded-lg border border-line bg-surface p-1 shadow-pop">
            {rest.map((tab) => (
              <button key={tab.value} type="button" role="menuitemradio" aria-checked={value === tab.value}
                onClick={() => { onChange(tab.value); setOpen(false) }}
                className={`min-h-10 rounded-md px-3 text-left text-sm whitespace-nowrap outline-none hover:bg-surface-2 focus-visible:bg-surface-2 ${value === tab.value ? 'font-semibold text-primary' : ''}`}>
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// How many tabs fit into `room` px: the widths of the tabs and of "Ещё ˅" last; 8 px of the row's padding, 2 px gaps.
// When the chosen tab is among the hidden ones, the "Ещё" button carries its name — then it is as wide as that tab + ˅
export const MORE_ARROW = 20
export function tabsThatFit(widths, room, active = -1) {
  const tabs = widths.slice(0, -1)
  const sum = (n) => tabs.slice(0, n).reduce((a, w) => a + w, 0) + Math.max(0, n - 1) * 2 + 8
  if (sum(tabs.length) <= room) return tabs.length
  const moreFor = (n) => (active >= n ? tabs[active] + MORE_ARROW : widths[widths.length - 1])
  let n = tabs.length - 1
  while (n > 1 && sum(n) + 2 + moreFor(n) > room) n -= 1
  return n
}

// A media query as a value (false where there is no window: the tests, the server)
export function useMedia(query) {
  const get = () => Boolean(globalThis.matchMedia?.(query).matches)
  const [on, setOn] = useState(get)
  useEffect(() => {
    const m = globalThis.matchMedia?.(query)
    if (!m) return undefined
    const change = () => setOn(m.matches)
    change()
    m.addEventListener('change', change)
    return () => m.removeEventListener('change', change)
  }, [query])
  return on
}

// True while a row that scrolls sideways has more to the right (its right edge then fades)
export function useEdgeFade(ref, enabled = true) {
  const [more, setMore] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || !enabled) { setMore(false); return undefined }
    const check = () => setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 4)
    check()
    el.addEventListener('scroll', check, { passive: true })
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(check)
    ro?.observe(el)
    return () => { el.removeEventListener('scroll', check); ro?.disconnect() }
  }, [ref, enabled])
  return more
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

// Phase 17.3: one empty state for the storefront, the cabinet and the admin — an icon in a grey circle, a title, a
// line of explanation, in the middle of a block at most 544 px wide (never stretched over a wide work area);
// `action` = { label, to | onClick, icon } — the blue button of the next step (or any buttons as children)
export function EmptyState({ icon: Icon = SearchX, title, hint, action, compact = false, className = '', children }) {
  const ActionIcon = action?.icon
  return (
    <div data-testid="empty-state" className={`mx-auto flex w-full max-w-[34rem] flex-col items-center px-4 text-center ${compact ? 'py-6' : 'py-12'} ${className}`}>
      <span className="flex size-14 items-center justify-center rounded-full bg-surface-2 text-muted"><Icon className="size-7" aria-hidden /></span>
      <p className="mt-4 text-h3">{title}</p>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
      {action && (
        <Button className="mt-4" to={action.to} onClick={action.onClick}>
          {ActionIcon && <ActionIcon className="size-4" aria-hidden />}{action.label}
        </Button>
      )}
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
