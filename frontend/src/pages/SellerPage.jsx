import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import { ChartLine, CirclePlus, History, LayoutDashboard, Package, Store } from 'lucide-react'
import AddFromCatalog from '../components/AddFromCatalog'
import { ModeChoice } from '../components/ImportSummary'
import { ErrorText } from '../components/AuthForm'
import { useToast } from '../components/overlays'
import { Badge, Button, Card, Input, Select, Skeleton, inputClass } from '../components/ui'
import { STORE_CITIES } from '../config/cities'
import api, { errorKey } from '../services/api'
import { importTitle } from '../services/format'

const STORE_FIELDS = ['name', 'inn_stir', 'phone', 'telegram', 'city', 'district', 'address']
const FIELD_LABELS = { inn_stir: 'innStir' }
const CURRENCIES = ['USD', 'UZS']
const ACCEPT = '.xlsx,.xls,.csv,.pdf'

function StoreForm({ store, onSaved }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() =>
    Object.fromEntries(STORE_FIELDS.map((f) => [f, store?.[f] ?? ''])))
  const [error, setError] = useState('')
  const toast = useToast()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    // Empty optional fields are sent as null
    const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))
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

function ImportHistory({ items }) {
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
              {imp.source === 'file' && `${t(`upload.modes.${imp.mode}`)} · `}{imp.currency} · {new Date(imp.created_at).toLocaleString('ru-RU')} · {t(`import.status.${imp.status}`)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

const SECTIONS = [
  { to: '/seller', key: 'overview', icon: LayoutDashboard, end: true },
  { to: '/seller/goods', key: 'goods', icon: Package },
  { to: '/seller/add', key: 'add', icon: CirclePlus },
  { to: '/seller/imports', key: 'imports', icon: History },
  { to: '/seller/analytics', key: 'analytics', icon: ChartLine },
  { to: '/seller/profile', key: 'profile', icon: Store },
]

// Cabinet menu: a column on the left on a computer, scrolling tabs on top on a phone
function CabinetNav() {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('cabinet.menu')} className="-mx-4 min-w-0 overflow-x-auto px-4 [scrollbar-width:none] md:mx-0 md:overflow-visible md:px-0">
      <ul className="flex gap-1 border-b border-line md:sticky md:top-24 md:flex-col md:border-b-0">
        {SECTIONS.map(({ to, key, icon: Icon, end }) => (
          <li key={key} className="shrink-0">
            <NavLink to={to} end={end} className={({ isActive }) => `flex min-h-11 items-center gap-2.5 px-3 text-sm font-medium whitespace-nowrap outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary md:rounded-md ${
              isActive ? 'border-b-2 border-primary text-primary md:border-b-0 md:bg-primary-soft' : 'border-b-2 border-transparent text-muted hover:text-ink md:border-b-0 md:hover:bg-surface-2'}`}>
              <Icon className="size-4 shrink-0" aria-hidden />{t(`cabinet.nav.${key}`)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

// Seller cabinet: the store profile first; then the menu and the chosen section
export default function SellerLayout() {
  const { t } = useTranslation()
  const [store, setStore] = useState(undefined)
  const [imports, setImports] = useState(null)

  useEffect(() => {
    api.get('/stores/me').then((res) => setStore(res.data)).catch(() => setStore(null))
  }, [])

  const loadImports = () => api.get('/imports').then((res) => setImports(res.data)).catch(() => setImports([]))
  useEffect(() => {
    if (store) loadImports()
  }, [store?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (store === undefined) return <Skeleton className="h-64 w-full rounded-xl" />
  // Without a store profile goods can't be added in any way
  if (!store) return <StoreForm store={store} onSaved={setStore} />
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-[12rem_minmax(0,1fr)] md:gap-8">
      <div className="min-w-0">
        <p className="mb-2 hidden truncate px-3 text-xs font-semibold tracking-wide text-faint uppercase md:block">{store.name}</p>
        <CabinetNav />
      </div>
      <div className="min-w-0">
        {imports === null
          ? <Skeleton className="h-64 w-full rounded-xl" />
          // The currency the seller chose last time is the default everywhere
          : <Outlet context={{ store, setStore, imports, loadImports, defaultCurrency: imports[0]?.currency || 'USD' }} />}
      </div>
      <span className="sr-only">{t('cabinet.title')}</span>
    </div>
  )
}

export function AddSection() {
  const { defaultCurrency, loadImports } = useOutletContext()
  const [params] = useSearchParams()
  return <AddGoods defaultCurrency={defaultCurrency} onAdded={loadImports} initialMethod={params.get('method')} />
}

export function ImportsSection() {
  const { imports } = useOutletContext()
  return <ImportHistory items={imports} />
}

export function ProfileSection() {
  const { store, setStore } = useOutletContext()
  return <StoreForm store={store} onSaved={setStore} />
}
