import { useState } from 'react'
import { Undo2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { UndoSummary } from './ImportSummary'
import { Modal, useToast } from './overlays'
import { Button, Skeleton } from './ui'

// "Undo this upload" (phase 12): the summary "what will come back" first, then the undo itself.
// Shown only for the store's last published file or post, not older than 7 days (can_undo / overview.undo)
export default function UndoUpload({ importId, onDone, size = 'sm', variant = 'secondary', className = '' }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [summary, setSummary] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const errorText = (err) => t([`undo.error.${err.response?.data?.detail?.code}`, 'undo.error.failed'])

  const show = () => {
    setOpen(true)
    setSummary(null)
    setError('')
    api.get(`/imports/${importId}/undo`).then((res) => setSummary(res.data)).catch((err) => setError(errorText(err)))
  }

  const confirm = async () => {
    setBusy(true)
    try {
      const res = await api.post(`/imports/${importId}/undo`)
      setOpen(false)
      toast(t('undo.done', { conflicts: res.data.conflicts }))
      onDone?.(res.data)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button size={size} variant={variant} className={className} onClick={show}>
        <Undo2 className="size-4" aria-hidden />{t('undo.button')}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={t('undo.title')} fullOnPhone
        footer={<>
          <Button variant="secondary" onClick={() => setOpen(false)}>{t('undo.keep')}</Button>
          <Button variant="danger" onClick={confirm} disabled={busy || !summary}>{busy ? t('undo.undoing') : t('undo.confirm')}</Button>
        </>}>
        {error && <p role="alert" className="mb-2 text-sm text-danger">{error}</p>}
        {summary ? <UndoSummary summary={summary} /> : !error && <Skeleton className="h-32 w-full rounded-lg" />}
      </Modal>
    </>
  )
}
