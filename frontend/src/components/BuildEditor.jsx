import { Plus, Search, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import api, { errorKey } from '../services/api'
import { SLOTS, SLOT_CATEGORIES, missingRequired, toPayloadPart } from '../services/builds'
import { specLabel, useSpecDictionary } from '../services/specs'
import { ProductLine } from './AddFromCatalog'
import { ErrorText } from './AuthForm'
import { Button, Card, Checkbox, Input, Select, Tabs, inputClass } from './ui'

const CURRENCIES = ['USD', 'UZS']
const PURPOSES = ['gaming', 'office', 'work', 'other']
const MODES = ['exact', 'specs', 'none']
// Modifiers and service values say nothing about a part of a ready PC
const HIDDEN_SPECS = ['box', 'revision', 'external', 'ecc', 'modules']
let nextKey = 1
export const newPart = (slot) => ({ key: `n${nextKey++}`, slot, mode: 'specs', product: null,
  category: SLOT_CATEGORIES[slot]?.[0] || null, specs: {}, raw_text: '', quantity: 1 })

// "Choose the exact model": the catalog search of the slot's categories
function PartSearch({ part, onPick }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [found, setFound] = useState(null)
  const timer = useRef()
  useEffect(() => {
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setFound(null); return }
    timer.current = setTimeout(() => {
      api.get('/seller/builds/search', { params: { q, slot: part.slot === 'other' ? undefined : part.slot } })
        .then((res) => setFound(res.data)).catch(() => setFound([]))
    }, 300)
  }, [q, part.slot])
  return (
    <div>
      <label className="relative block">
        <Search className="pointer-events-none absolute top-3 left-3 size-4 text-faint" aria-hidden />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('sellerBuilds.searchPlaceholder')}
          aria-label={t('sellerBuilds.search')} className={`${inputClass} pl-9`} />
      </label>
      {found && (
        <ul className="mt-1 max-h-60 overflow-y-auto rounded-md border border-line">
          {found.length === 0 && <li className="p-3 text-sm text-muted">{t('sellerBuilds.searchEmpty')}</li>}
          {found.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => onPick(p)} className="w-full px-3 py-2 text-left hover:bg-surface-2">
                <ProductLine product={p} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// "Only specs": the dictionary fields of the category (lists and numbers); a CPU adds its model
function SpecFields({ part, dictionary, onChange }) {
  const { t } = useTranslation()
  const set = (key, value) => onChange({ specs: { ...part.specs, [key]: value === '' ? undefined : value } })
  if (part.slot === 'gpu' && part.specs.integrated) return null
  const fields = (dictionary?.[part.category] || []).filter((s) => !HIDDEN_SPECS.includes(s.key))
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {part.slot === 'storage' && (
        <Select label={t('sellerBuilds.storageType')} value={part.category} onChange={(e) => onChange({ category: e.target.value, specs: {} })}>
          {SLOT_CATEGORIES.storage.map((c) => <option key={c} value={c}>{t(`categories.${c}`)}</option>)}
        </Select>
      )}
      {part.slot === 'cpu' && (
        <Input label={t('sellerBuilds.cpuModel')} placeholder={t('sellerBuilds.cpuModelPlaceholder')} value={part.specs.model || ''}
          onChange={(e) => set('model', e.target.value)} />
      )}
      {fields.map((s) => {
        const value = part.specs[s.key] ?? ''
        const label = specLabel(s.key, part.category)
        if (s.kind === 'number') {
          return <Input key={s.key} type="number" min="0" step="any" label={`${label}, ${t(`specs.unitShort.${s.unit}`, { defaultValue: s.unit })}`}
            value={value} onChange={(e) => set(s.key, e.target.value === '' ? '' : Number(e.target.value))} />
        }
        if (s.kind === 'yesno') {
          return (
            <Select key={s.key} label={label} value={value === '' ? '' : value ? '1' : '0'} onChange={(e) => set(s.key, e.target.value === '' ? '' : e.target.value === '1')}>
              <option value="">—</option><option value="1">{t('specs.yes')}</option><option value="0">{t('specs.no')}</option>
            </Select>
          )
        }
        if (s.values?.length) {
          return (
            <Select key={s.key} label={label} value={value} onChange={(e) => set(s.key, e.target.value)}>
              <option value="">—</option>
              {s.values.map((v) => <option key={v} value={v}>{t(`specs.values.${s.key}`, { returnObjects: true })?.[v] || v}</option>)}
            </Select>
          )
        }
        return <Input key={s.key} label={label} value={value} onChange={(e) => set(s.key, e.target.value)} />
      })}
    </div>
  )
}

function PartRow({ part, dictionary, onChange, onRemove }) {
  const { t } = useTranslation()
  const modes = MODES.filter((m) => m !== 'specs' || part.slot !== 'other')
  return (
    <li className="grid grid-cols-[minmax(0,1fr)] gap-3 rounded-lg border border-line p-3">
      <div className="flex items-end gap-2">
        <Select className="min-w-0 flex-1" label={t('sellerBuilds.slot')} value={part.slot}
          onChange={(e) => onChange({ slot: e.target.value, category: SLOT_CATEGORIES[e.target.value]?.[0] || null, specs: {}, product: null,
            mode: e.target.value === 'other' && part.mode === 'specs' ? 'none' : part.mode })}>
          {SLOTS.map((s) => <option key={s} value={s}>{t(`builds.slot.${s}`)}</option>)}
        </Select>
        <Input className="w-20" type="number" min="1" max="8" label={t('sellerBuilds.quantity')} value={part.quantity}
          onChange={(e) => onChange({ quantity: e.target.value })} />
        <Button type="button" variant="text" size="sm" onClick={onRemove} aria-label={t('sellerBuilds.removePart')} title={t('sellerBuilds.removePart')} className="mb-1">
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>
      {/* Three tabs don't fit a phone: there it is a list */}
      <div className="hidden sm:block">
        <Tabs label={t('sellerBuilds.modeLabel')} value={part.mode} onChange={(mode) => onChange({ mode })}
          tabs={modes.map((m) => ({ value: m, label: t(`sellerBuilds.mode.${m}`) }))} />
      </div>
      <Select className="sm:hidden" aria-label={t('sellerBuilds.modeLabel')} value={part.mode} onChange={(e) => onChange({ mode: e.target.value })}>
        {modes.map((m) => <option key={m} value={m}>{t(`sellerBuilds.mode.${m}`)}</option>)}
      </Select>
      {part.mode === 'exact' && (part.product ? (
        <div className="flex items-start justify-between gap-3 rounded-md bg-surface-2 p-2.5">
          <ProductLine product={part.product} />
          <Button type="button" variant="secondary" size="sm" onClick={() => onChange({ product: null })}>{t('sellerBuilds.change')}</Button>
        </div>
      ) : <PartSearch part={part} onPick={(product) => onChange({ product })} />)}
      {part.mode === 'specs' && (
        <>
          {part.slot === 'gpu' && <Checkbox label={t('sellerBuilds.integrated')} checked={Boolean(part.specs.integrated)}
            onChange={(e) => onChange({ specs: e.target.checked ? { integrated: true } : {} })} />}
          <SpecFields part={part} dictionary={dictionary} onChange={onChange} />
        </>
      )}
      {(part.mode === 'none' || part.raw_text) && (
        <Input label={t('sellerBuilds.sellerText')} placeholder={t('sellerBuilds.sellerTextPlaceholder')} value={part.raw_text}
          onChange={(e) => onChange({ raw_text: e.target.value })} />
      )}
    </li>
  )
}

// The build form: price and the rest, parts by slots with three precision levels each. A draft of a pasted post
// comes here too, so the seller checks every part before publishing
export default function BuildEditor({ initial, buildId, defaultCurrency, onSaved, onCancel }) {
  const { t } = useTranslation()
  const dictionary = useSpecDictionary()
  const [form, setForm] = useState(() => ({
    name: initial?.name || '', price: initial?.price ?? '', currency: initial?.currency || defaultCurrency || 'USD',
    condition: ['new', 'used'].includes(initial?.condition) ? initial.condition : initial ? '' : 'new',
    purpose: initial?.purpose || 'gaming', is_in_stock: initial?.is_in_stock ?? true, description: initial?.description || '',
  }))
  const [parts, setParts] = useState(() => initial?.parts || ['cpu', 'motherboard', 'ram', 'gpu', 'storage', 'psu'].map(newPart))
  const [error, setError] = useState('')
  const [tried, setTried] = useState(false)
  const [busy, setBusy] = useState(false)
  const missing = missingRequired(parts)

  const change = (key, patch) => setParts((list) => list.map((p) => (p.key === key ? { ...p, ...patch } : p)))
  const onSubmit = async (e) => {
    e.preventDefault()
    setTried(true)
    if (missing.length) return
    setBusy(true)
    setError('')
    const body = { ...form, price: Number(form.price), text: initial?.text, components: parts.map(toPayloadPart) }
    try {
      const res = buildId ? await api.put(`/seller/builds/${buildId}`, body) : await api.post('/seller/builds', body)
      onSaved(res.data)
    } catch (err) {
      const code = err.response?.data?.detail?.code
      setError(code ? t(`sellerBuilds.error.${code}`, { defaultValue: t(errorKey(err)) }) : t(errorKey(err)))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <Card className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <Input label={t('sellerBuilds.name')} placeholder={t('sellerBuilds.namePlaceholder')} required minLength={2} value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Input type="number" min="0" step="any" required label={t('sellerBuilds.price')} value={form.price}
            onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <Select label={t('sellerBuilds.currency')} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}
            hint={initial?.currency_check ? t('sellerBuilds.currencyCheck') : undefined}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
          <Select label={t('sellerBuilds.condition')} required value={form.condition} onChange={(e) => setForm({ ...form, condition: e.target.value })}
            hint={initial?.condition_check && form.condition === 'used' ? t('sellerBuilds.conditionCheck') : undefined}>
            <option value="" disabled>{t('sellerBuilds.conditionChoose')}</option>
            {['new', 'used'].map((c) => <option key={c} value={c}>{t(`builds.condition.${c}`)}</option>)}
          </Select>
          <Select label={t('sellerBuilds.purpose')} value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>
            {PURPOSES.map((p) => <option key={p} value={p}>{t(`builds.purpose.${p}`)}</option>)}
          </Select>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm text-muted">{t('sellerBuilds.description')}</span>
          <textarea rows={3} className={inputClass} placeholder={t('sellerBuilds.descriptionPlaceholder')} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </label>
        <Checkbox label={t('sellerBuilds.inStock')} checked={form.is_in_stock} onChange={(e) => setForm({ ...form, is_in_stock: e.target.checked })} />
      </Card>

      <Card className="grid grid-cols-[minmax(0,1fr)] gap-3">
        <div>
          <h2 className="text-h3">{t('sellerBuilds.parts')}</h2>
          <p className="mt-1 text-sm text-muted">{t('sellerBuilds.partsHint')}</p>
        </div>
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3">
          {parts.map((p) => (
            <PartRow key={p.key} part={p} dictionary={dictionary} onChange={(patch) => change(p.key, patch)}
              onRemove={() => setParts((list) => list.filter((x) => x.key !== p.key))} />
          ))}
        </ul>
        <Button type="button" variant="secondary" className="justify-self-start" onClick={() => setParts([...parts, newPart('other')])}>
          <Plus className="size-4" aria-hidden />{t('sellerBuilds.addPart')}
        </Button>
      </Card>

      {(tried || initial?.parts) && missing.length > 0 && (
        <div role="alert" className="grid gap-1 rounded-md border border-warning-line bg-warning-soft p-3 text-sm text-warning">
          {missing.map((slot) => (
            <p key={slot} className="flex gap-1.5"><TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />{t(`sellerBuilds.required.${slot}`)}</p>
          ))}
        </div>
      )}
      <ErrorText>{error}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>{buildId ? t('sellerBuilds.save') : t('sellerBuilds.publish')}</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>{t('sellerBuilds.cancel')}</Button>
      </div>
    </form>
  )
}
