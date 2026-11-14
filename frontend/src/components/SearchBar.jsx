import { ChevronDown, Crosshair, LoaderCircle, MapPin, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { CITIES, detectCity } from '../config/cities'
import api from '../services/api'
import { checkBarcode, looksLikeBarcode } from '../services/barcode'
import { useCity } from '../services/city.jsx'
import { Dropdown, DropdownItem } from './overlays'

const SEARCH_DELAY_MS = 300
// Phase 16.2: the search row lives under the header on these pages; elsewhere a magnifier in the header opens it
export const SEARCH_ROW_PATHS = ['/', '/catalog']

// Where the search goes: the catalog with the words; the other filters of the catalog stay
export function catalogSearch(text, currentSearch = '') {
  const next = new URLSearchParams(currentSearch)
  if (text) next.set('q', text)
  else next.delete('q')
  next.delete('page')
  return { pathname: '/catalog', search: next.toString() }
}

// City choice: "Определить" first (asks the browser only on a click), then the list
export function CityMenu({ className = '', initialOpen = false }) {
  const { t } = useTranslation()
  const { city, setCity } = useCity()
  const [busy, setBusy] = useState(false)
  const detect = async () => {
    setBusy(true)
    setCity(await detectCity())
    setBusy(false)
  }
  return (
    <Dropdown align="left" initialOpen={initialOpen} panelClassName="max-h-96 w-60 overflow-y-auto" trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={`${t('nav.city')}: ${t(`cities.${city}`)}`} title={t('nav.city')}
        className={`flex h-full min-h-11 items-center gap-1.5 text-sm font-medium outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset ${className}`}>
        {busy ? <LoaderCircle className="size-4 shrink-0 animate-spin text-primary" aria-hidden /> : <MapPin className="size-4 shrink-0 text-primary" aria-hidden />}
        <span className="hidden truncate sm:inline">{t(`cities.${city}`)}</span>
        <ChevronDown className="size-4 shrink-0 text-muted" aria-hidden />
      </button>
    )}>
      <DropdownItem icon={Crosshair} onClick={detect} className="font-medium text-primary">{t('search.detect')}</DropdownItem>
      <div className="my-1 border-t border-line" />
      {CITIES.map((c) => (
        <DropdownItem key={c} selected={c === city} onClick={() => setCity(c)}>{t(`cities.${c}`)}</DropdownItem>
      ))}
    </Dropdown>
  )
}

// One row, one height, one white background: words → city → "Найти".
// Phase 17.1: no overflow-hidden on the row — it cut off the city list (the button lit up, the list did not show)
// In the catalog the results follow the typing (through the address); elsewhere "Найти"/Enter opens the catalog
export default function SearchBar({ autoFocus = false, className = '' }) {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const input = useRef(null)
  const onCatalog = location.pathname === '/catalog'
  const urlQuery = onCatalog ? new URLSearchParams(location.search).get('q') || '' : null
  const [value, setValue] = useState(urlQuery || '')

  useEffect(() => { if (autoFocus) input.current?.focus() }, [autoFocus])

  // The address changed from outside (logo, "back"): the field follows it
  useEffect(() => {
    if (urlQuery !== null && urlQuery !== value.trim()) setValue(urlQuery)
  }, [urlQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  // Phase 12.3: a code from a box opens its card — only a code confirmed in the common base
  const go = async (text, replace) => {
    if (looksLikeBarcode(text) && !checkBarcode(text).error) {
      const id = await api.get(`/catalog/barcode/${encodeURIComponent(checkBarcode(text).code)}`).then((r) => r.data.product_id).catch(() => null)
      if (id) { navigate(`/products/${id}`); return }
    }
    navigate(catalogSearch(text, onCatalog ? location.search : ''), { replace })
  }

  useEffect(() => {
    if (!onCatalog || value.trim() === urlQuery) return
    const timer = setTimeout(() => go(value.trim(), true), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [value]) // eslint-disable-line react-hooks/exhaustive-deps

  const onSubmit = (e) => {
    e.preventDefault()
    go(value.trim(), onCatalog)
  }

  return (
    <form role="search" onSubmit={onSubmit}
      className={`flex h-12 min-w-0 items-stretch rounded-lg border border-line-strong bg-surface shadow-card focus-within:border-primary focus-within:ring-2 focus-within:ring-primary-soft ${className}`}>
      <label className="relative flex min-w-0 flex-1 items-center">
        <Search className="pointer-events-none absolute left-3 size-5 text-muted" aria-hidden />
        <input ref={input} type="search" enterKeyHint="search" value={value} onChange={(e) => setValue(e.target.value)}
          placeholder={t('search.placeholder')} aria-label={t('search.placeholder')}
          className="h-full w-full min-w-0 bg-transparent pr-2 pl-10 text-base text-ink outline-none placeholder:text-faint md:text-sm" />
      </label>
      <div className="flex shrink-0 border-l border-line">
        <CityMenu className="max-w-56 px-2.5 sm:px-3" />
      </div>
      <button type="submit"
        className="shrink-0 rounded-r-[calc(var(--radius-lg)-1px)] bg-primary px-4 text-sm font-semibold text-white outline-none hover:bg-primary-hover focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-inset md:px-7">
        {t('home.searchSubmit')}
      </button>
    </form>
  )
}
