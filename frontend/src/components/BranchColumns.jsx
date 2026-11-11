import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Columns3, Store } from 'lucide-react'
import api, { errorKey } from '../services/api'
import { ErrorText } from './AuthForm'
import { branchLabel } from './BranchStock'
import { Button, Card } from './ui'

// Upload: "весь магазин / только филиал …" (phase 12.1); hidden for a store with one branch
export function ScopeChoice({ branches, value, onChange }) {
  const { t } = useTranslation()
  if (!branches || branches.length < 2) return null
  return (
    <label className="mt-4 block">
      <span className="text-sm text-muted">{t('branchImport.scope')}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="mt-2 h-11 w-full min-w-0 rounded-md border border-line-strong bg-surface px-3 text-sm md:max-w-md">
        <option value="">{t('branchImport.wholeStore')}</option>
        {branches.map((b) => <option key={b.id} value={b.id}>{t('branchImport.onlyBranch', { branch: branchLabel(b) })}</option>)}
      </select>
      <span className="mt-1 block text-xs text-muted">{t(value ? 'branchImport.onlyHint' : 'branchImport.wholeHint')}</span>
    </label>
  )
}

// The preview: "сопоставление столбцов" — which price-list column is which branch; the match is remembered
export function ColumnsMatch({ imp, branches, onConfirmed, readOnly }) {
  const { t } = useTranslation()
  const info = imp.branch_info || {}
  const [mapping, setMapping] = useState(() => ({ ...(info.mapping || {}) }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!info.headers?.length) return null

  const confirm = async () => {
    setBusy(true)
    setError('')
    try {
      const res = await api.post(`/imports/${imp.id}/columns`, { mapping })
      onConfirmed(res.data)
    } catch (err) {
      const code = err.response?.data?.detail?.code
      setError(t(code ? `branchImport.error.${code}` : errorKey(err)))
    }
    setBusy(false)
  }
  return (
    <Card className={info.confirmed ? '' : 'border-primary'}>
      <h2 className="flex items-center gap-2 text-h3"><Columns3 className="size-5 text-primary" aria-hidden />{t('branchImport.title')}</h2>
      <p className="mt-1 text-sm text-muted">{t(info.confirmed ? 'branchImport.confirmedHint' : 'branchImport.hint')}</p>
      <ul className="mt-3 grid gap-2 md:grid-cols-2">
        {info.headers.map((h) => (
          <li key={h} className="grid min-w-0 gap-1">
            <span className="truncate text-sm font-medium" title={h}>«{h}»</span>
            <select value={mapping[h] ?? ''} disabled={readOnly} aria-label={t('branchImport.columnFor', { column: h })}
              onChange={(e) => setMapping({ ...mapping, [h]: e.target.value ? Number(e.target.value) : null })}
              className="h-10 w-full min-w-0 rounded-md border border-line-strong bg-surface px-2 text-sm">
              <option value="">{t('branchImport.notBranch')}</option>
              {branches.map((b) => <option key={b.id} value={b.id}>{branchLabel(b)}</option>)}
            </select>
          </li>
        ))}
      </ul>
      <ErrorText>{error}</ErrorText>
      {!readOnly && (
        <Button className="mt-3" size="sm" variant={info.confirmed ? 'secondary' : 'primary'} disabled={busy} onClick={confirm}>
          {t(info.confirmed ? 'branchImport.update' : 'branchImport.confirm')}
        </Button>
      )}
    </Card>
  )
}

// "What will change" by branch: how many goods appear / run out in each branch
export function BranchChanges({ items }) {
  const { t } = useTranslation()
  if (!items?.length) return null
  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className="text-sm font-medium">{t('branchImport.changes')}</p>
      <ul className="mt-1 grid gap-1 text-sm">
        {items.map((b) => (
          <li key={b.branch_id} className="flex flex-wrap items-center gap-x-2">
            <Store className="size-4 text-faint" aria-hidden />
            <span className="font-medium">{b.name || b.address}</span>
            {b.appear > 0 && <span className="text-success">{t('branchImport.appear', { count: b.appear })}</span>}
            {b.run_out > 0 && <span className="text-danger">{t('branchImport.runOut', { count: b.run_out })}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
