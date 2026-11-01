import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import AddFromCatalog from '../components/AddFromCatalog'
import { ErrorText } from '../components/AuthForm'
import api, { errorKey } from '../services/api'
import { importTitle } from '../services/format'

const STORE_FIELDS = ['name', 'inn_stir', 'phone', 'telegram', 'address', 'district']
const FIELD_LABELS = { inn_stir: 'innStir' }
const CURRENCIES = ['USD', 'UZS']
const ACCEPT = '.xlsx,.xls,.csv,.pdf'

function StoreForm({ store, onSaved }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() =>
    Object.fromEntries(STORE_FIELDS.map((f) => [f, store?.[f] ?? ''])))
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaved(false)
    // Empty optional fields are sent as null
    const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))
    try {
      const res = await api.put('/stores/me', payload)
      setSaved(true)
      onSaved(res.data)
    } catch (err) {
      setError(t(errorKey(err)))
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-line bg-surface shadow-card p-6">
      <h2 className="text-h2">{t('store.title')}</h2>
      {!store && <p className="mt-1 text-sm text-muted">{t('store.createHint')}</p>}
      {store && (
        <p className={`mt-1 text-sm ${store.is_verified ? 'text-success' : 'text-muted'}`}>
          {t(store.is_verified ? 'store.verified' : 'store.notVerified')}
        </p>
      )}
      <div className="mt-4 grid grid-cols-2 gap-4">
        {STORE_FIELDS.map((f) => (
          <label key={f} className="block">
            <span className="mb-1 block text-sm text-muted">{t(`store.${FIELD_LABELS[f] || f}`)}</span>
            <input
              value={form[f]} required={f === 'name'} minLength={f === 'name' ? 2 : undefined}
              onChange={(e) => setForm({ ...form, [f]: e.target.value })}
              className="w-full rounded-md border border-line-strong px-3 py-2 outline-none focus:border-primary"
            />
          </label>
        ))}
      </div>
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <div className="flex items-center gap-3">
        <button className="rounded-md bg-primary px-4 py-2 text-white hover:bg-slate-700">{t('store.save')}</button>
        {saved && <span className="text-sm text-success">{t('store.saved')}</span>}
      </div>
    </form>
  )
}

function CurrencyChoice({ currency, onChange, label }) {
  const { t } = useTranslation()
  return (
    <div className="mt-4 flex items-center gap-4">
      <span className="text-sm text-muted">{t(label)}</span>
      {CURRENCIES.map((c) => (
        <label key={c} className="flex items-center gap-1.5 text-sm">
          <input type="radio" name="currency" checked={currency === c} onChange={() => onChange(c)} />
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
        className={`mt-4 cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition ${
          dragging ? 'border-primary bg-surface-2' : 'border-line-strong hover:border-primary'}`}
      >
        <p className="font-medium">{file ? file.name : t('upload.drop')}</p>
        <p className="mt-1 text-sm text-muted">{t('upload.formats')}</p>
        <input ref={inputRef} type="file" accept={ACCEPT} hidden
          onChange={(e) => e.target.files[0] && setFile(e.target.files[0])} />
      </div>
      <CurrencyChoice currency={currency} onChange={setCurrency} label="upload.currency" />
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <button
        onClick={onSubmit} disabled={!file || busy}
        className="rounded-md bg-primary px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {busy ? t('auth.loading') : t('upload.submit')}
      </button>
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
        className="w-full rounded-md border border-line-strong px-3 py-2 font-mono text-sm outline-none focus:border-primary" />
      <CurrencyChoice currency={currency} onChange={setCurrency} label="manual.textCurrency" />
      <div className="mt-4"><ErrorText>{error}</ErrorText></div>
      <button onClick={onSubmit} disabled={text.trim().length < 3 || busy}
        className="rounded-md bg-primary px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50">
        {busy ? t('auth.loading') : t('upload.submit')}
      </button>
    </div>
  )
}

const METHODS = ['file', 'text', 'catalog']

// Three ways to add goods side by side, with a hint when each one is handy
function AddGoods({ defaultCurrency, onAdded }) {
  const { t } = useTranslation()
  const [method, setMethod] = useState('file')
  return (
    <div className="rounded-xl border border-line bg-surface shadow-card p-6">
      <h2 className="text-h2">{t('manual.title')}</h2>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {METHODS.map((m) => (
          <button key={m} type="button" onClick={() => setMethod(m)}
            className={`rounded-lg border p-3 text-left transition ${
              method === m ? 'border-primary bg-surface-2' : 'border-line hover:border-primary'}`}>
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
    </div>
  )
}

function ImportHistory({ items }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-xl border border-line bg-surface shadow-card p-6">
      <h2 className="text-h2">{t('upload.history')}</h2>
      {items.length === 0 && <p className="mt-2 text-sm text-muted">{t('upload.empty')}</p>}
      <ul className="mt-2 divide-y divide-line">
        {items.map((imp) => (
          <li key={imp.id} className="flex items-center justify-between py-2 text-sm">
            <span className="min-w-0 truncate">
              <span className="mr-2 rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{t(`manual.source.${imp.source}`)}</span>
              {imp.source === 'manual'
                ? <span className="font-medium">{importTitle(imp)}</span>
                : <Link to={`/seller/imports/${imp.id}`} className="font-medium hover:underline">{importTitle(imp)}</Link>}
            </span>
            <span className="shrink-0 pl-3 text-muted">
              {imp.currency} · {new Date(imp.created_at).toLocaleString('ru-RU')} · {t(`import.status.${imp.status}`)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function SellerPage() {
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

  if (store === undefined) return null
  // Without a store profile goods can't be added in any way
  if (!store) return <StoreForm store={store} onSaved={setStore} />
  if (imports === null) return null
  return (
    <div className="grid gap-6">
      <Link to="/seller/analytics" className="flex items-center justify-between rounded-xl border border-line bg-surface shadow-card px-6 py-4 hover:border-primary">
        <span><span className="font-semibold">{t('market.analyticsTitle')}</span><span className="ml-3 text-sm text-muted">{t('market.analyticsHint')}</span></span>
        <span aria-hidden>→</span>
      </Link>
      {/* The currency the seller chose last time is the default everywhere */}
      <AddGoods defaultCurrency={imports[0]?.currency || 'USD'} onAdded={loadImports} />
      <ImportHistory items={imports} />
      <StoreForm store={store} onSaved={setStore} />
    </div>
  )
}
