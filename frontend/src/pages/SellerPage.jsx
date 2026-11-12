import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useLocation, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import { Boxes, ChartLine, Check, ChevronDown, ExternalLink, House, LogOut, MapPin, Package, Store, Users } from 'lucide-react'
import AddFromCatalog from '../components/AddFromCatalog'
import BranchesBlock from '../components/Branches'
import StockModeBlock, { WarehouseBlock } from '../components/StockMode'
import { ScanBox, ScanPanel } from '../components/ScanPanel'
import { stockTabs } from './WarehousePage'
import { PLACE_OPEN, placeFor, placeLabel, placesOf, readPlace, savePlace } from '../services/place'
import { ScopeChoice } from '../components/BranchColumns'
import { ModeChoice } from '../components/ImportSummary'
import UndoUpload from '../components/UndoUpload'
import { ErrorText } from '../components/AuthForm'
import { Avatar, UnreadBadge } from '../components/Header'
import { Dropdown, DropdownItem, useToast } from '../components/overlays'
import { Badge, Button, Card, Input, Select, Skeleton, inputClass } from '../components/ui'
import { STORE_CITIES } from '../config/cities'
import { isYandexMapsUrl } from '../config/maps'
import { linkProps, storeUrl } from '../config/sites'
import Workspace, { pageActive, sectionActive } from '../layouts/Workspace'
import { NotificationBell } from '../components/Notifications'
import { BlockedNotice } from '../components/AdminDecisions'
import api, { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { useUnread } from '../services/chat'
import { useNewReservations } from '../services/reservations'
import { importTitle } from '../services/format'
import LangSwitch from '../components/LangSwitch'
import i18n from '../i18n'
import { intlLocale } from '../services/lang'

const STORE_FIELDS = ['name', 'inn_stir', 'phone', 'telegram', 'city', 'district', 'address', 'hours', 'map_url', 'reservation_days']
// Hints under the fields: where to go matters to the buyer (phase 12)
const FIELD_HINTS = { address: 'addressHint', hours: 'hoursHint', map_url: 'mapHint' }
const FIELD_LABELS = { inn_stir: 'innStir' }
// Once the store has branches, where to go is edited per branch (phase 12.1)
const LOCATION_FIELDS = ['city', 'district', 'address', 'hours', 'map_url']
const CURRENCIES = ['USD', 'UZS']
const ACCEPT = '.xlsx,.xls,.csv,.pdf'

function StoreForm({ store, onSaved }) {
  const { t } = useTranslation()
  const fields = store?.branches?.length ? STORE_FIELDS.filter((f) => !LOCATION_FIELDS.includes(f)) : STORE_FIELDS
  const [form, setForm] = useState(() =>
    Object.fromEntries(fields.map((f) => [f, String(store?.[f] ?? (f === 'reservation_days' ? 2 : ''))])))
  const [error, setError] = useState('')
  const [mapError, setMapError] = useState(false)
  const toast = useToast()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.map_url != null && !isYandexMapsUrl(form.map_url)) {
      setMapError(true)
      return
    }
    // Empty optional fields are sent as null
    const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))
    payload.reservation_days = Number(payload.reservation_days) || 2
    try {
      const res = await api.put('/stores/me', payload)
      toast(t('store.saved'))
      onSaved(res.data)
    } catch (err) {
      if (err.response?.data?.detail?.code === 'map_url') setMapError(true)
      else setError(t(errorKey(err)))
    }
  }

  return (
    <Card as="form" onSubmit={onSubmit}>
      <h2 className="text-h2">{t('store.title')}</h2>
      {!store && <p className="mt-1 text-sm text-muted">{t('store.createHint')}</p>}
      {store && (
        <p className={`mt-1 text-sm ${store.is_verified ? 'text-success' : 'text-muted'}`}>
          {t(store.is_verified ? 'store.verified' : 'store.notVerified')}
        </p>
      )}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {fields.map((f) => (f === 'city' ? (
          <Select key={f} label={t('store.city')} value={form.city} required hint={t('store.cityHint')}
            onChange={(e) => setForm({ ...form, city: e.target.value })}>
            <option value="" disabled>{t('store.cityChoose')}</option>
            {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
          </Select>
        ) : f === 'reservation_days' ? (
          <Input key={f} type="number" min={1} max={7} label={t('store.reservation_days')} hint={t('store.reservationDaysHint')}
            value={form[f]} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
        ) : (
          <Input key={f} label={t(`store.${FIELD_LABELS[f] || f}`)} hint={FIELD_HINTS[f] && t(`store.${FIELD_HINTS[f]}`)}
            value={form[f]} required={f === 'name' || f === 'address'} minLength={f === 'name' ? 2 : f === 'address' ? 3 : undefined}
            className={f === 'address' || f === 'map_url' ? 'md:col-span-2' : ''}
            inputMode={f === 'map_url' ? 'url' : undefined}
            placeholder={f === 'map_url' ? 'https://yandex.uz/maps/-/…' : f === 'hours' ? t('store.hoursPlaceholder') : undefined}
            error={f === 'map_url' && mapError ? t('store.mapError') : undefined}
            onChange={(e) => { setForm({ ...form, [f]: e.target.value }); if (f === 'map_url') setMapError(false) }} />
        )))}
      </div>
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <Button type="submit">{t('store.save')}</Button>
    </Card>
  )
}

function CurrencyChoice({ currency, onChange, label }) {
  const { t } = useTranslation()
  return (
    <div className="mt-4 flex min-h-7 flex-wrap items-center gap-x-4 gap-y-1">
      <span className="text-sm text-muted">{t(label)}</span>
      {CURRENCIES.map((c) => (
        <label key={c} className="flex items-center gap-1.5 text-sm">
          <input type="radio" className="size-4 accent-primary" name="currency" checked={currency === c} onChange={() => onChange(c)} />
          {c}
        </label>
      ))}
    </div>
  )
}

function UploadBox({ defaultCurrency }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [currency, setCurrency] = useState(defaultCurrency)
  const [mode, setMode] = useState(null) // "full" / "append": the seller always chooses
  const [scope, setScope] = useState('') // phase 12.1: '' = the whole store, else the branch id
  const branches = useOutletContext()?.store?.branches || []
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0])
  }

  const onSubmit = async () => {
    setError('')
    setBusy(true)
    const body = new FormData()
    body.append('file', file)
    body.append('currency', currency)
    body.append('mode', mode)
    if (scope) body.append('branch_id', scope)
    try {
      const res = await api.post('/imports', body)
      navigate(`/seller/imports/${res.data.id}`)
    } catch (err) {
      setError(t(errorKey(err)))
      setBusy(false)
    }
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`mt-4 cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors md:p-10 ${
          dragging ? 'border-primary bg-primary-soft' : 'border-line-strong hover:border-primary'}`}
      >
        <p className="font-medium break-words">{file ? file.name : t('upload.drop')}</p>
        <p className="mt-1 text-sm text-muted">{t('upload.formats')}</p>
        <input ref={inputRef} type="file" accept={ACCEPT} hidden
          onChange={(e) => e.target.files[0] && setFile(e.target.files[0])} />
      </div>
      <CurrencyChoice currency={currency} onChange={setCurrency} label="upload.currency" />
      <ScopeChoice branches={branches} value={scope} onChange={setScope} />
      <ModeChoice mode={mode} onChange={setMode} />
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      {file && !mode && <p className="mb-2 text-sm text-warning">{t('upload.modeRequired')}</p>}
      <Button onClick={onSubmit} disabled={!file || !mode || busy}>
        {busy ? t('auth.loading') : t('upload.submit')}
      </Button>
    </div>
  )
}

// "Paste as text": a Telegram post goes through the same parsing and preview as a file
function TextBox({ defaultCurrency }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [currency, setCurrency] = useState(defaultCurrency)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const onSubmit = async () => {
    setError('')
    setBusy(true)
    try {
      const res = await api.post('/imports/text', { text, currency })
      navigate(`/seller/imports/${res.data.id}`)
    } catch (err) {
      setError(t(errorKey(err)))
      setBusy(false)
    }
  }

  return (
    <div>
      <textarea value={text} rows={10} placeholder={t('manual.textPlaceholder')} onChange={(e) => setText(e.target.value)}
        className={`${inputClass} font-mono`} />
      <CurrencyChoice currency={currency} onChange={setCurrency} label="manual.textCurrency" />
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <Button onClick={onSubmit} disabled={text.trim().length < 3 || busy}>
        {busy ? t('auth.loading') : t('upload.submit')}
      </Button>
    </div>
  )
}

const METHODS = ['scan', 'catalog', 'file', 'text']

// The ways to add goods side by side, with a hint when each one is handy; phase 12.4: "Отсканировать коробку" first
function AddGoods({ defaultCurrency, onAdded, initialMethod }) {
  const { t } = useTranslation()
  const [method, setMethod] = useState(METHODS.includes(initialMethod) ? initialMethod : 'scan')
  return (
    <Card>
      <h2 className="text-h2">{t('manual.title')}</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {METHODS.map((m) => (
          <button key={m} type="button" onClick={() => setMethod(m)}
            className={`rounded-lg border p-3 text-left transition-colors ${
              method === m ? 'border-primary bg-primary-soft' : 'border-line hover:border-primary'}`}>
            <p className="font-medium">{t(`manual.method.${m}`)}</p>
            <p className="mt-1 text-xs text-muted">{t(`manual.methodHint.${m}`)}</p>
          </button>
        ))}
      </div>
      <div className="mt-6">
        {method === 'scan' && <ScanBox onAdded={onAdded} />}
        {method === 'file' && <UploadBox defaultCurrency={defaultCurrency} />}
        {method === 'text' && <TextBox defaultCurrency={defaultCurrency} />}
        {method === 'catalog' && <AddFromCatalog defaultCurrency={defaultCurrency} onAdded={onAdded} />}
      </div>
    </Card>
  )
}

function ImportHistory({ items, onChanged }) {
  const { t } = useTranslation()
  return (
    <Card>
      <h2 className="text-h2">{t('upload.history')}</h2>
      {items.length === 0 && <p className="mt-2 text-sm text-muted">{t('upload.empty')}</p>}
      <ul className="mt-2 divide-y divide-line">
        {items.map((imp) => (
          <li key={imp.id} className="flex flex-col justify-between gap-x-3 gap-y-0.5 py-2 text-sm md:flex-row md:items-center">
            <span className="min-w-0 break-words md:flex-1 md:truncate">
              <Badge className="mr-2">{t(`manual.source.${imp.source}`)}</Badge>
              {imp.source === 'manual'
                ? <span className="font-medium">{importTitle(imp)}</span>
                : <Link to={`/seller/imports/${imp.id}`} className="font-medium hover:underline">{importTitle(imp)}</Link>}
            </span>
            <span className="shrink-0 text-xs text-muted md:text-sm">
              {imp.source === 'file' && `${t(`upload.modes.${imp.mode}`)} · `}{imp.currency} · {new Date(imp.created_at).toLocaleString(intlLocale(i18n.language))} · {imp.status === 'undone'
                ? <Badge tone="warning">{t('import.status.undone')}</Badge> : t(`import.status.${imp.status}`)}
            </span>
            {imp.can_undo && <UndoUpload importId={imp.id} onDone={onChanged} className="self-start md:self-auto" />}
          </li>
        ))}
      </ul>
    </Card>
  )
}

// Phase 12.5: four sections without sub-items on the left (Товары · Склад · Покупатели · Аналитика); the pages of a
// section are tabs at the top of the page. "Главная" (the overview) is the logo; on a phone — the first tab of the
// bottom bar. The store profile and the storefront are in the avatar menu.
export function sellerSections(store, badges = {}) {
  const stock = store?.stock_mode === 'stock'
    ? stockTabs(store).map((k) => ({ to: `/seller/stock?tab=${k}`, key: `stock_${k}` }))
    : [{ to: '/seller/stock', key: 'stock_about' }]
  const buyers = (badges.messages || 0) + (badges.reservations || 0)
  return [
    { to: '/seller', key: 'overview', icon: House, end: true, tab: true, side: false },
    { to: '/seller/goods', key: 'goodsGroup', icon: Package, tab: true, pages: [
      { to: '/seller/goods', key: 'goods' }, { to: '/seller/add', key: 'add' },
      { to: '/seller/builds', key: 'builds', deep: true }, { to: '/seller/imports', key: 'imports', deep: true }] },
    { to: '/seller/stock', key: 'stock', icon: Boxes, tab: true, pages: stock },
    { to: '/seller/messages', key: 'buyers', icon: Users, tab: true, badge: buyers || undefined, pages: [
      { to: '/seller/messages', key: 'messages', deep: true, badge: badges.messages },
      { to: '/seller/reservations', key: 'reservations', badge: badges.reservations }] },
    { to: '/seller/analytics', key: 'analyticsGroup', icon: ChartLine, tab: true, pages: [
      { to: '/seller/analytics', key: 'analytics' }, { to: '/seller/reports', key: 'reports' }] },
  ]
}

// The pages of the open section as tabs at the top: one row that scrolls sideways on a phone
export function SectionTabs({ sections }) {
  const { t } = useTranslation()
  const location = useLocation()
  const group = sections.find((s) => s.pages && sectionActive(s, location))
  if (!group || group.pages.length < 2) return null
  return (
    <nav aria-label={t('cabinet.sectionTabs')} className="mb-4 flex max-w-full gap-0.5 overflow-x-auto overscroll-x-contain rounded-md bg-surface-2 p-1 [scrollbar-width:none] sm:inline-flex">
      {group.pages.map((c) => {
        const active = pageActive(c, location)
        return (
          <Link key={c.key} to={c.to} aria-current={active ? 'page' : undefined}
            className={`inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-sm px-3 text-sm font-medium whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              active ? 'bg-surface text-primary shadow-card' : 'text-muted hover:text-ink'}`}>
            {t(`cabinet.nav.${c.key}`)}<UnreadBadge count={c.badge} />
          </Link>
        )
      })}
    </nav>
  )
}

// "Юнусабад ▾" with a pin in the top bar: the warehouse and the branches, one place for the whole cabinet
export function PlaceMenu({ places, place, setPlace }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener(PLACE_OPEN, show)
    return () => window.removeEventListener(PLACE_OPEN, show)
  }, [])
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  if (places.length < 2) return null
  return (
    <div ref={box} className="relative min-w-0">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="listbox"
        aria-label={t('place.choose')} title={t('place.choose')}
        className="flex min-h-10 max-w-[7.5rem] min-w-0 items-center gap-1 rounded-md px-1.5 text-sm font-semibold outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary sm:max-w-56 sm:px-2.5">
        <MapPin className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="truncate">{placeLabel(t, place)}</span>
        <ChevronDown className="size-4 shrink-0 text-muted" aria-hidden />
      </button>
      {open && (
        <ul role="listbox" aria-label={t('place.choose')}
          className="absolute top-full right-0 z-40 mt-2 max-h-80 w-56 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-line bg-surface p-1.5 shadow-pop">
          {places.map((p) => (
            <li key={p.id}>
              <button type="button" role="option" aria-selected={p.id === place?.id} onClick={() => { setPlace(p.id); setOpen(false) }}
                className={`flex min-h-10 w-full items-center gap-2 rounded-md px-2.5 text-left text-sm hover:bg-surface-2 ${p.id === place?.id ? 'font-semibold text-primary' : ''}`}>
                <span className="min-w-0 flex-1 truncate">{placeLabel(t, p)}</span>
                {p.id === place?.id && <Check className="size-4 shrink-0" aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AccountMenu({ store }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <Dropdown trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={t('nav.account')} title={user.email}
        className="shrink-0 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
        <Avatar email={user.email} className="size-9 text-sm" />
      </button>
    )}>
      <div className="mb-1.5 border-b border-line p-2.5 pb-3">
        {store && <p className="truncate text-sm font-semibold" title={store.name}>{store.name}</p>}
        <p className="truncate text-xs text-muted" title={user.email}>{user.email}</p>
      </div>
      {store && <DropdownItem as={Link} to="/seller/profile" icon={Store}>{t('cabinet.nav.profile')}</DropdownItem>}
      {/* The storefront opens in a new tab: the cabinet stays where the seller left it */}
      <DropdownItem as="a" href={storeUrl('/')} target="_blank" rel="noreferrer" icon={ExternalLink}>{t('seller.openStore')}</DropdownItem>
      <DropdownItem icon={LogOut} onClick={() => { logout(); navigate('/seller/login') }}>{t('nav.logout')}</DropdownItem>
      {/* Phase 15: on a phone the language is chosen here, the top bar stays short */}
      <div className="mt-1.5 border-t border-line p-2 sm:hidden"><LangSwitch wide /></div>
    </Dropdown>
  )
}

// The frame of every seller page apart from the storefront; `sections` only for a logged-in seller with a store
function SellerFrame({ store, sections, top, place, children }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <Workspace home="/seller" subtitle={t('seller.subtitle')} sections={sections} navKey="cabinet.nav" tabKey="cabinet.tab"
      menuLabel={t('cabinet.menu')} sideTitle={store?.name} top={top}
      actions={<>
        {place && <PlaceMenu {...place} />}
        <LangSwitch className={user?.role === 'seller' ? 'hidden sm:flex' : ''} />
        {user?.role === 'seller' && store && <NotificationBell allPath="/seller/notifications" />}
        {user?.role === 'seller' && <AccountMenu store={store} />}
      </>}>
      {children}
    </Workspace>
  )
}

// Login and register of sellers: the cabinet frame without the menu
export function SellerAuthLayout() {
  return <SellerFrame><Outlet /></SellerFrame>
}

// A buyer (or anyone but a seller) opened /seller/...
export function NotSellerPage() {
  const { t } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  return (
    <SellerFrame>
      <Card className="mx-auto max-w-md text-center md:mt-4 md:!p-8">
        <Store className="mx-auto size-10 text-primary" aria-hidden />
        <h1 className="mt-4 text-h1">{t('seller.notSellerTitle')}</h1>
        <p className="mt-2 text-sm text-muted">{t('seller.notSellerText')}</p>
        <div className="mt-6 grid gap-2">
          <Button size="lg" onClick={() => { logout(); navigate('/seller/login') }}>{t('seller.loginAsSeller')}</Button>
          <Button size="lg" variant="secondary" {...linkProps(storeUrl('/'))}>{t('seller.backToStore')}</Button>
        </div>
      </Card>
    </SellerFrame>
  )
}

// Seller cabinet: the store profile first; then the menu and the chosen section
export default function SellerLayout() {
  const [store, setStore] = useState(undefined)
  const [imports, setImports] = useState(null)
  const unread = useUnread(!!store)
  const newReservations = useNewReservations(!!store)
  const badges = { messages: unread, reservations: newReservations }
  const location = useLocation()
  const places = placesOf(store)
  const [placeId, setPlaceId] = useState(readPlace)
  const place = placeFor(places, placeId)
  const setPlace = (id) => { setPlaceId(id); savePlace(id) }
  // The scanner's panel: on every page without its own scanning ("Склад" modes, "Отсканировать коробку")
  const ownScan = location.pathname.startsWith('/seller/stock') || location.pathname.startsWith('/seller/add')

  useEffect(() => {
    api.get('/stores/me').then((res) => setStore(res.data)).catch(() => setStore(null))
  }, [])

  const loadImports = () => api.get('/imports').then((res) => setImports(res.data)).catch(() => setImports([]))
  useEffect(() => {
    if (store) loadImports()
  }, [store?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  let content
  if (store === undefined || (store && imports === null)) content = <Skeleton className="h-64 w-full rounded-xl" />
  // Without a store profile goods can't be added in any way
  else if (!store) content = <div className="mx-auto max-w-3xl"><StoreForm store={store} onSaved={setStore} /></div>
  // The currency the seller chose last time is the default everywhere
  else {
    content = (
      <>
        <BlockedNotice store={store} />
        <Outlet context={{ store, setStore, imports, loadImports, defaultCurrency: imports[0]?.currency || 'USD', place, setPlace, places }} />
        <ScanPanel enabled={!ownScan} place={place} stockMode={store.stock_mode === 'stock'} />
      </>
    )
  }
  const sections = store ? sellerSections(store, badges) : null
  const top = sections && <SectionTabs sections={sections} />
  return <SellerFrame store={store} sections={sections} top={top} place={store && { places, place, setPlace }}>{content}</SellerFrame>
}

export function AddSection() {
  const { defaultCurrency, loadImports } = useOutletContext()
  const [params] = useSearchParams()
  return <AddGoods defaultCurrency={defaultCurrency} onAdded={loadImports} initialMethod={params.get('method')} />
}

export function ImportsSection() {
  const { imports, loadImports } = useOutletContext()
  return <ImportHistory items={imports} onChanged={loadImports} />
}

export function ProfileSection() {
  const { store, setStore } = useOutletContext()
  return (
    <div className="grid gap-6">
      <StoreForm key={store.branches?.length ? 'b' : 's'} store={store} onSaved={setStore} />
      <BranchesBlock store={store} onChanged={setStore} />
      <StockModeBlock store={store} onChanged={setStore} />
      <WarehouseBlock store={store} onChanged={setStore} />
    </div>
  )
}
