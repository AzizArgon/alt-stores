import { useState } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import api, { errorKey } from '../services/api'
import { Modal, useToast } from './overlays'
import { Button } from './ui'

// Phase 17.6: cancel an unpublished upload (parsing, waiting for publication or failed). The preview rows are
// deleted, offers and prices stay as they are; a published upload is undone with UndoUpload instead
export const CANCELLABLE = ['processing', 'ready', 'failed']

export default function CancelImport({ importId, onDone, size = 'sm', className = '' }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const confirm = async () => {
    setBusy(true)
    setError('')
    try {
      const res = await api.post(`/imports/${importId}/cancel`)
      setOpen(false)
      toast(t('import.cancel.done'))
      onDone?.(res.data)
    } catch (err) {
      setError(t(errorKey(err, { 409: 'import.cancel.error' })))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button size={size} variant="secondary" className={className} onClick={() => { setError(''); setOpen(true) }}>
        <X className="size-4" aria-hidden />{t('import.cancel.button')}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={t('import.cancel.title')}
        footer={<>
          <Button variant="secondary" onClick={() => setOpen(false)}>{t('import.cancel.back')}</Button>
          <Button variant="danger" onClick={confirm} disabled={busy}>{busy ? t('import.cancel.cancelling') : t('import.cancel.button')}</Button>
        </>}>
        {error && <p role="alert" className="mb-2 text-sm text-danger">{error}</p>}
        <p className="text-sm">{t('import.cancel.text')}</p>
      </Modal>
    </>
  )
}
