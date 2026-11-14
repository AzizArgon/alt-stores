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
// Phase 16.2: the search row lives under the header on these pages; elsewhere a magnifier in the header opens it.
// Phase 17.1: on the home page the row is inside the blue banner (HERO_PATH), in the catalog it is compact
export const SEARCH_ROW_PATHS = ['/', '/catalog']
export const HERO_PATH = '/'

// Where the search goes: the catalog with the words; the other filters of the catalog stay
export function catalogSearch(text, currentSearch = '') {
  const next = new URLSearchParams(currentSearch)
  if (text) next.set('q', text)
  else next.delete('q')
  next.delete('page')
  return { pathname: '/catalog', search: next.toString() }
}

// City choice: "Определить" first (asks the browser only on a click), then the list
// `align`: where the list opens from — 'left' when the city is the first part of the row, 'right' when it is near the end
export function CityMenu({ className = '', initialOpen = false, align = 'left' }) {
  const { t } = useTranslation()
  const { city, setCity } = useCity()
  const [busy, setBusy] = useState(false)
  const detect = async () => {
    setBusy(true)
    setCity(await detectCity())
    setBusy(false)
  }
  return (
    <Dropdown align={align} initialOpen={initialOpen} panelClassName="max-h-96 w-60 overflow-y-auto" trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={`${t('nav.city')}: ${t(`cities.${city}`)}`} title={t('nav.city')}
        className={`flex h-full items-center gap-1.5 text-sm font-medium outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset ${className}`}>
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

// Phase 17.1, two looks of one row:
// `hero` — in the blue banner of the home page: city → words → "Найти";
// `compact` — under the header of the catalog (and from the magnifier): words → city → "Найти", 40 px like the filters
// Phase 17.1: no overflow-hidden on the row — it cut off the city list (the button lit up, the list did not show)
// In the catalog the results follow the typing (through the address); elsewhere "Найти"/Enter opens the catalog
export default function SearchBar({ autoFocus = false, className = '', variant = 'compact' }) {
  const hero = variant === 'hero'
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const input = useRef(null)
  const onCatalog = location.pathname === '/catalog'
  const urlQuery = onCatalog ? new URLSearchParams(location.search).get('q') || '' : null
  const [value, setValue] = useState(urlQuery || '')
  const placeholder = t(hero ? 'home.searchPlaceholder' : 'search.placeholder')

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

  const field = (
    <label className="relative flex min-w-0 flex-1 items-center">
      <Search className={`pointer-events-none absolute text-muted ${hero ? 'left-3.5 size-5' : 'left-3 size-4'}`} aria-hidden />
      <input ref={input} type="search" enterKeyHint="search" value={value} onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder} aria-label={placeholder}
        className={`h-full w-full min-w-0 bg-transparent pr-2 text-base text-ink outline-none placeholder:text-faint md:text-sm ${hero ? 'pl-11' : 'pl-9'}`} />
    </label>
  )
  const city = (
    <div className={`flex shrink-0 ${hero ? 'border-r' : 'border-l'} border-line`}>
      <CityMenu align={hero ? 'left' : 'right'} className={hero ? 'min-h-12 max-w-56 rounded-l-[calc(var(--radius-lg)-1px)] px-3' : 'max-w-52 px-2.5 text-[13px]'} />
    </div>
  )
  return (
    <form role="search" onSubmit={onSubmit} data-variant={variant}
      className={`flex min-w-0 items-stretch border bg-surface focus-within:border-primary focus-within:ring-2 focus-within:ring-primary-soft ${hero
        ? 'h-13 rounded-lg border-transparent text-ink shadow-pop'
        : 'h-10 w-full rounded-md border-line-strong md:max-w-[680px]'} ${className}`}>
      {hero ? <>{city}{field}</> : <>{field}{city}</>}
      <button type="submit"
        className={`shrink-0 bg-primary text-sm font-semibold text-white outline-none hover:bg-primary-hover focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-inset ${hero
          ? 'm-1 rounded-md px-4 md:px-7'
          : 'rounded-r-[calc(var(--radius-md)-1px)] px-3.5'}`}>
        {t('home.searchSubmit')}
      </button>
    </form>
  )
}
