import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MapPin, Pencil, Phone, Plus, Star, Trash2 } from 'lucide-react'
import { STORE_CITIES } from '../config/cities'
import { isYandexMapsUrl } from '../config/maps'
import api from '../services/api'
import { Modal, useToast } from './overlays'
import StoreWhere from './StoreWhere'
import { Badge, Button, Card, Input, Select } from './ui'
import { ErrorText } from './AuthForm'

const FIELDS = ['name', 'city', 'address', 'landmark', 'hours', 'phone', 'map_url']

// The branch title: its own name or the address ("Чиланзар" / "ул. Навои, 12")
export const branchTitle = (b) => b?.name || b?.address || ''

function BranchForm({ branch, onClose, onSaved }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [form, setForm] = useState(() => Object.fromEntries(FIELDS.map((f) => [f, String(branch?.[f] ?? (f === 'city' ? 'tashkent' : ''))])))
  const [error, setError] = useState('')
  const [mapError, setMapError] = useState(false)
  const set = (f) => (e) => { setForm({ ...form, [f]: e.target.value }); if (f === 'map_url') setMapError(false) }

  const save = async (e) => {
    e?.preventDefault()
    setError('')
    if (!isYandexMapsUrl(form.map_url)) return setMapError(true)
    const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))
    try {
      const res = branch ? await api.put(`/stores/me/branches/${branch.id}`, payload) : await api.post('/stores/me/branches', payload)
      toast(t('branches.saved'))
      onSaved(res.data)
    } catch (err) {
      const code = err.response?.data?.detail?.code
      if (code === 'map_url') setMapError(true)
      else setError(t(code ? `branches.error.${code}` : 'errors.network'))
    }
  }

  return (
    <Modal open onClose={onClose} fullOnPhone title={t(branch ? 'branches.edit' : 'branches.add')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('branches.cancel')}</Button><Button onClick={save}>{t('branches.save')}</Button></>}>
      <form onSubmit={save} className="grid gap-4">
        <Input label={t('branches.name')} hint={t('branches.nameHint')} value={form.name} onChange={set('name')} maxLength={100} />
        <Select label={t('store.city')} value={form.city} onChange={set('city')} required>
          {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
        </Select>
        <Input label={t('branches.address')} value={form.address} onChange={set('address')} required minLength={3} maxLength={255} />
        <Input label={t('branches.landmark')} hint={t('branches.landmarkHint')} value={form.landmark} onChange={set('landmark')} required minLength={2} maxLength={128} />
        <Input label={t('store.hours')} placeholder={t('store.hoursPlaceholder')} value={form.hours} onChange={set('hours')} maxLength={100} />
        <Input label={t('store.phone')} hint={t('branches.phoneHint')} value={form.phone} onChange={set('phone')} inputMode="tel" maxLength={32} />
        <Input label={t('store.map_url')} hint={t('store.mapHint')} value={form.map_url} onChange={set('map_url')} inputMode="url"
          placeholder="https://yandex.uz/maps/-/…" error={mapError ? t('store.mapError') : undefined} maxLength={500} />
        <ErrorText>{error}</ErrorText>
        <button type="submit" hidden />
      </form>
    </Modal>
  )
}

// Cabinet -> Store profile -> "Branches": the list as cards (phone and PC), add, change, delete, make the main one
export default function BranchesBlock({ store, onChanged }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [editing, setEditing] = useState(null) // null | 'new' | branch
  const [error, setError] = useState('')
  const branches = store.branches || []

  const act = async (fn, done) => {
    setError('')
    try {
      const res = await fn()
      onChanged(res.data)
      toast(t(done))
    } catch (err) {
      const code = err.response?.data?.detail?.code
      setError(t(code ? `branches.error.${code}` : 'errors.network'))
    }
  }
  const remove = (b) => {
    if (window.confirm(t('branches.deleteConfirm', { name: branchTitle(b) })))
      act(() => api.delete(`/stores/me/branches/${b.id}`), 'branches.deleted')
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-h2">{t('branches.title')}</h2>
          <p className="mt-1 text-sm text-muted">{t('branches.hint')}</p>
        </div>
        <Button size="sm" onClick={() => setEditing('new')}><Plus className="size-4" aria-hidden />{t('branches.add')}</Button>
      </div>
      <ErrorText>{error}</ErrorText>
      {!branches.length && <p className="mt-4 text-sm text-muted">{t('branches.none')}</p>}
      <ul className="mt-4 grid gap-3 md:grid-cols-2">
        {branches.map((b) => (
          <li key={b.id} className="min-w-0 rounded-lg border border-line p-3" data-testid="branch-card">
            <div className="flex flex-wrap items-center gap-2">
              <MapPin className="size-4 shrink-0 text-faint" aria-hidden />
              <span className="min-w-0 break-words font-medium">{b.name || t(`cities.${b.city}`)}</span>
              {b.is_main && <Badge tone="primary">{t('branches.main')}</Badge>}
            </div>
            <StoreWhere store={b} buttons={false} className="mt-2" />
            {b.phone && <p className="mt-1 flex gap-1.5 text-sm text-muted"><Phone className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />{b.phone}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => setEditing(b)}><Pencil className="size-4" aria-hidden />{t('branches.edit')}</Button>
              {!b.is_main && (
                <>
                  <Button size="sm" variant="secondary" onClick={() => act(() => api.post(`/stores/me/branches/${b.id}/main`), 'branches.madeMain')}>
                    <Star className="size-4" aria-hidden />{t('branches.makeMain')}</Button>
                  <Button size="sm" variant="text" onClick={() => remove(b)} aria-label={t('branches.delete')}>
                    <Trash2 className="size-4" aria-hidden />{t('branches.delete')}</Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
      {editing && (
        <BranchForm branch={editing === 'new' ? null : editing} onClose={() => setEditing(null)}
          onSaved={(s) => { setEditing(null); onChanged(s) }} />
      )}
    </Card>
  )
}
