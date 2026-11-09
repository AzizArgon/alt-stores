import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import { CalendarCheck, ChartLine, CirclePlus, ExternalLink, History, LayoutDashboard, LogOut, MessageSquare, Monitor, Package, Store } from 'lucide-react'
import AddFromCatalog from '../components/AddFromCatalog'
import { ModeChoice } from '../components/ImportSummary'
import UndoUpload from '../components/UndoUpload'
import { ErrorText } from '../components/AuthForm'
import { Avatar } from '../components/Header'
import { Dropdown, DropdownItem, useToast } from '../components/overlays'
import { Badge, Button, Card, Input, Select, Skeleton, inputClass } from '../components/ui'
import { STORE_CITIES } from '../config/cities'
import { linkProps, storeUrl } from '../config/sites'
import Workspace from '../layouts/Workspace'
import api, { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { useUnread } from '../services/chat'
import { useNewReservations } from '../services/reservations'
import { importTitle } from '../services/format'

const STORE_FIELDS = ['name', 'inn_stir', 'phone', 'telegram', 'city', 'district', 'address', 'reservation_days']
const FIELD_LABELS = { inn_stir: 'innStir' }
const CURRENCIES = ['USD', 'UZS']
const ACCEPT = '.xlsx,.xls,.csv,.pdf'

function StoreForm({ store, onSaved }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() =>
    Object.fromEntries(STORE_FIELDS.map((f) => [f, String(store?.[f] ?? (f === 'reservation_days' ? 2 : ''))])))
  const [error, setError] = useState('')
  const toast = useToast()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    // Empty optional fields are sent as null
    const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))
    payload.reservation_days = Number(payload.reservation_days) || 2
    try {
      const res = await api.put('/stores/me', payload)
      toast(t('store.saved'))
      onSaved(res.data)
    } catch (err) {
      setError(t(errorKey(err)))
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
        {STORE_FIELDS.map((f) => (f === 'city' ? (
          <Select key={f} label={t('store.city')} value={form.city} required hint={t('store.cityHint')}
            onChange={(e) => setForm({ ...form, city: e.target.value })}>
            <option value="" disabled>{t('store.cityChoose')}</option>
            {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
          </Select>
        ) : f === 'reservation_days' ? (
          <Input key={f} type="number" min={1} max={7} label={t('store.reservation_days')} hint={t('store.reservationDaysHint')}
            value={form[f]} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
        ) : (
          <Input key={f} label={t(`store.${FIELD_LABELS[f] || f}`)}
            value={form[f]} required={f === 'name'} minLength={f === 'name' ? 2 : undefined}
            onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
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

const METHODS = ['file', 'text', 'catalog']

// Three ways to add goods side by side, with a hint when each one is handy
function AddGoods({ defaultCurrency, onAdded, initialMethod }) {
  const { t } = useTranslation()
  const [method, setMethod] = useState(METHODS.includes(initialMethod) ? initialMethod : 'file')
  return (
    <Card>
      <h2 className="text-h2">{t('manual.title')}</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
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
            <span className="min-w-0 break-words md:truncate">
              <Badge className="mr-2">{t(`manual.source.${imp.source}`)}</Badge>
              {imp.source === 'manual'
                ? <span className="font-medium">{importTitle(imp)}</span>
                : <Link to={`/seller/imports/${imp.id}`} className="font-medium hover:underline">{importTitle(imp)}</Link>}
            </span>
            <span className="shrink-0 text-xs text-muted md:text-sm">
              {imp.source === 'file' && `${t(`upload.modes.${imp.mode}`)} · `}{imp.currency} · {new Date(imp.created_at).toLocaleString('ru-RU')} · {imp.status === 'undone'
                ? <Badge tone="warning">{t('import.status.undone')}</Badge> : t(`import.status.${imp.status}`)}
            </span>
            {imp.can_undo && <UndoUpload importId={imp.id} onDone={onChanged} className="self-start md:self-auto" />}
          </li>
        ))}
      </ul>
    </Card>
  )
}

const SECTIONS = [
  { to: '/seller', key: 'overview', icon: LayoutDashboard, end: true, tab: true },
  { to: '/seller/goods', key: 'goods', icon: Package, tab: true },
  { to: '/seller/builds', key: 'builds', icon: Monitor, tab: true },
  { to: '/seller/add', key: 'add', icon: CirclePlus, tab: true },
  { to: '/seller/messages', key: 'messages', icon: MessageSquare, tab: true },
  { to: '/seller/reservations', key: 'reservations', icon: CalendarCheck, tab: true },
  // Not in the phone bar (8 tabs do not fit 360 px): the history opens from the overview's last upload
  { to: '/seller/imports', key: 'imports', icon: History },
  { to: '/seller/analytics', key: 'analytics', icon: ChartLine, tab: true },
  { to: '/seller/profile', key: 'profile', icon: Store },
]

// The storefront always opens in a new tab: the cabinet stays where the seller left it
function OpenStoreButton() {
  const { t } = useTranslation()
  return (
    <Button href={storeUrl('/')} target="_blank" rel="noreferrer" variant="secondary" size="sm"
      aria-label={t('seller.openStore')} title={t('seller.openStore')} className="shrink-0 max-sm:!px-2.5">
      <ExternalLink className="size-4" aria-hidden /><span className="hidden sm:inline">{t('seller.openStore')}</span>
    </Button>
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
      <DropdownItem icon={LogOut} onClick={() => { logout(); navigate('/seller/login') }}>{t('nav.logout')}</DropdownItem>
    </Dropdown>
  )
}

// The frame of every seller page apart from the storefront; `sections` only for a logged-in seller with a store
function SellerFrame({ store, sections, children }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <Workspace home="/seller" subtitle={t('seller.subtitle')} sections={sections} navKey="cabinet.nav" tabKey="cabinet.tab"
      menuLabel={t('cabinet.menu')} sideTitle={store?.name}
      actions={<>
        {store && <span className="hidden max-w-56 truncate text-sm font-semibold lg:block" title={store.name}>{store.name}</span>}
        <OpenStoreButton />
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
  else content = <Outlet context={{ store, setStore, imports, loadImports, defaultCurrency: imports[0]?.currency || 'USD' }} />
  return <SellerFrame store={store} sections={store ? SECTIONS.map((s) => (badges[s.key] != null ? { ...s, badge: badges[s.key] } : s)) : null}>{content}</SellerFrame>
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
  return <StoreForm store={store} onSaved={setStore} />
}
