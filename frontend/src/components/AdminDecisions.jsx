// Phase 13, the seller's side of the admin panel: "Оспорить" next to an Anti-Fraud flag of his offer, the statuses
// of disputed flags, card fixes and barcodes the admin decided, and the notice of a blocked store.
import { Gavel, ShieldOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import api, { errorKey } from '../services/api'
import Flags from './Flags'
import { Modal, useToast } from './overlays'
import { Badge, Button, Card, inputClass } from './ui'

function DisputeModal({ flag, onClose, onDone }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  if (!flag) return null
  const send = async () => {
    if (!text.trim()) { setError(t('admin.error.comment_required')); return }
    try {
      await api.post(`/seller/flags/${flag.id}/dispute`, { comment: text.trim() })
      toast(t('flags.disputeSent'))
      onDone()
      onClose()
    } catch (err) {
      const code = err.response?.data?.detail?.code
      setError(t(code ? `admin.error.${code}` : errorKey(err)))
    }
  }
  return (
    <Modal open onClose={onClose} title={t('flags.disputeTitle')} footer={<>
      <Button variant="secondary" onClick={onClose}>{t('admin.cancel')}</Button>
      <Button onClick={send}>{t('flags.disputeSend')}</Button>
    </>}>
      <Flags flags={[flag]} className="mb-3 grid gap-1" />
      <p className="mb-2 text-sm text-muted">{t('flags.disputeHint')}</p>
      <label className="grid gap-1 text-sm font-medium">{t('flags.disputeComment')}
        <textarea rows={3} maxLength={500} value={text} onChange={(e) => setText(e.target.value)} className={`${inputClass} resize-y`} />
      </label>
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
    </Modal>
  )
}

// The offer editor: active flags with "Оспорить" (or the admin's answer) and the disputed / dismissed ones
export function SellerFlags({ offer, onChanged }) {
  const { t } = useTranslation()
  const [disputing, setDisputing] = useState(null)
  const active = offer.flags || []
  const others = offer.disputed_flags || []
  if (!active.length && !others.length) return null
  return (
    <div className="grid gap-2">
      {active.map((f) => (
        <div key={f.id ?? f.type} className="grid gap-1">
          <Flags flags={[f]} className="grid gap-1" />
          {f.resolution === 'upheld' ? (
            <p className="px-1 text-xs break-words text-muted"><Badge tone="warning">{t('flags.status.upheld')}</Badge> {t('flags.adminAnswer', { text: f.admin_answer })}</p>
          ) : f.id && (
            <Button size="sm" variant="text" className="justify-self-start" onClick={() => setDisputing(f)}>
              <Gavel className="size-4" aria-hidden />{t('flags.dispute')}
            </Button>
          )}
        </div>
      ))}
      {others.map((f) => (
        <p key={f.id} className="rounded-md border border-line bg-surface-2 px-2 py-1.5 text-xs break-words text-muted">
          <span className="font-semibold text-ink">{t(`flags.type.${f.type}`)}</span> — {t(`flags.status.${f.status}`)}
          {f.dispute_comment && <span className="block">{t('flags.yourComment', { text: f.dispute_comment })}</span>}
          {f.admin_answer && <span className="block">{t('flags.adminAnswer', { text: f.admin_answer })}</span>}
        </p>
      ))}
      <DisputeModal flag={disputing} onClose={() => setDisputing(null)} onDone={onChanged} />
    </div>
  )
}

export function BlockedNotice({ store }) {
  const { t } = useTranslation()
  if (!store?.blocked_at) return null
  return (
    <div role="alert" className="mb-5 flex gap-3 rounded-xl border border-danger-line bg-danger-soft p-4 text-danger">
      <ShieldOff className="size-5 shrink-0" aria-hidden />
      <div className="min-w-0 text-sm">
        <p className="font-semibold">{t('cabinet.decisions.blockedTitle')}</p>
        <p className="break-words">{t('cabinet.decisions.blockedText', { reason: store.block_reason })}</p>
      </div>
    </div>
  )
}

// The cabinet overview: what the admin decided about this store's requests
export function DecisionsBlock() {
  const { t } = useTranslation()
  const [data, setData] = useState(null)
  useEffect(() => { api.get('/seller/decisions').then((res) => setData(res.data)).catch(() => {}) }, [])
  if (!data) return null
  const { flags, fixes, barcodes } = data
  if (!flags.length && !fixes.length && !barcodes.length) return null
  const tone = { pending: 'neutral', accepted: 'success', rejected: 'danger' }
  return (
    <Card>
      <h2 className="text-h3">{t('cabinet.decisions.title')}</h2>
      <p className="mb-3 text-sm text-muted">{t('cabinet.decisions.hint')}</p>
      <div className="grid gap-4">
        {flags.length > 0 && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">{t('cabinet.decisions.flags')}</h3>
            <ul className="grid gap-1.5 text-sm">
              {flags.map((f) => (
                <li key={f.id} className="break-words">
                  <span className="font-medium">{f.product.name}</span> — {t(`flags.type.${f.type}`)}:{' '}
                  <Badge tone={f.status === 'disputed' ? 'neutral' : f.resolution === 'dismissed' ? 'success' : 'warning'}>
                    {t(`flags.status.${f.status === 'disputed' ? 'disputed' : f.resolution}`)}
                  </Badge>
                  {f.admin_answer && <span className="block text-muted">{t('flags.adminAnswer', { text: f.admin_answer })}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
        {fixes.length > 0 && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">{t('cabinet.decisions.fixes')}</h3>
            <ul className="grid gap-1.5 text-sm">
              {fixes.map((f) => (
                <li key={f.id} className="break-words">
                  <span className="font-medium">{f.before?.name}</span> → {f.after?.name || f.after?.model}{' '}
                  <Badge tone={tone[f.status]}>{t(`cabinet.decisions.fixStatus.${f.status}`)}</Badge>
                  {f.merged_into && <span className="ml-1 text-muted">{t('cabinet.decisions.merged')}</span>}
                  {f.reject_reason && <span className="block text-muted">{t('cabinet.decisions.rejectReason', { text: f.reject_reason })}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
        {barcodes.length > 0 && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">{t('cabinet.decisions.barcodes')}</h3>
            <ul className="grid gap-1.5 text-sm">
              {barcodes.map((b) => (
                <li key={b.id} className="break-words">
                  {t('cabinet.decisions.barcodeDisputed', { code: b.code, name: b.name })}
                  {b.chosen && <span className="block text-muted">{t('cabinet.decisions.barcodeChosen', { name: b.chosen })}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </Card>
  )
}
