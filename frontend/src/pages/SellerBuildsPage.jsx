import { ClipboardPaste, ExternalLink, ListChecks, Loader2, Monitor, Pencil, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import BuildEditor from '../components/BuildEditor'
import PhotoUploader from '../components/PhotoUploader'
import { PrecisionBadge } from '../components/BuildTile'
import { Modal, useToast } from '../components/overlays'
import Price from '../components/Price'
import { Badge, Button, Card, EmptyState, Skeleton, Tabs, inputClass } from '../components/ui'
import { storeUrl } from '../config/sites'
import api, { errorKey } from '../services/api'
import { toEditorPart } from '../services/builds'
import { formatDate } from '../services/format'

function TrustHint() {
  const { t } = useTranslation()
  return <p className="flex gap-2 rounded-md bg-info-soft p-3 text-sm text-info"><ListChecks className="mt-0.5 size-4 shrink-0" aria-hidden />{t('sellerBuilds.trust')}</p>
}

// "My builds": ready PCs apart from "My goods"; a price list upload never changes them
export default function SellerBuildsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [removing, setRemoving] = useState(null)

  const load = () => api.get('/seller/builds').then((res) => setData(res.data)).catch((err) => setError(t(errorKey(err))))
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setSale = async (build, onSale) => {
    await api.post(`/seller/builds/${build.id}/sale`, { on_sale: onSale })
    toast(t(onSale ? 'sellerBuilds.putBackDone' : 'sellerBuilds.tookOff'))
    load()
  }
  const remove = async () => {
    await api.delete(`/seller/builds/${removing.id}`)
    setRemoving(null)
    toast(t('sellerBuilds.deleted'))
    load()
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-h2 md:text-h1">{t('sellerBuilds.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('sellerBuilds.hint')}</p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <Button to="/seller/builds/new" className="flex-1 sm:flex-none"><Monitor className="size-4" aria-hidden />{t('sellerBuilds.byForm')}</Button>
          <Button to="/seller/builds/new?method=text" variant="secondary" className="flex-1 sm:flex-none"><ClipboardPaste className="size-4" aria-hidden />{t('sellerBuilds.byText')}</Button>
        </div>
      </div>
      <TrustHint />
      <ErrorText>{error}</ErrorText>
      {!data && !error && <Skeleton className="h-40 w-full rounded-xl" />}
      {data?.items.length === 0 && <EmptyState icon={Monitor} title={t('sellerBuilds.empty')} hint={t('sellerBuilds.emptyHint')} />}
      <ul className="grid gap-3">
        {data?.items.map((b) => (
          <Card as="li" key={b.id} padded={false} className={`p-4 ${b.is_in_stock ? '' : 'opacity-70'}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-1.5">
                  <Badge tone={b.is_in_stock ? 'success' : 'neutral'}>{t(b.is_in_stock ? 'sellerBuilds.onSale' : 'sellerBuilds.offSale')}</Badge>
                  <PrecisionBadge precision={b.precision} />
                  {b.warnings > 0 && <Badge tone="warning"><TriangleAlert className="size-3.5" aria-hidden />{t('builds.warnings')}</Badge>}
                </p>
                <p className="mt-1.5 font-semibold break-words">{b.name}</p>
                <p className="text-xs text-muted">
                  {t(`builds.purpose.${b.purpose}`)} · {t(`builds.condition.${b.condition}`)} · {t('builds.updated', { date: formatDate(b.updated_at) })}
                </p>
              </div>
              <Price price={b.price} currency={b.currency} usdRate={data.usd_rate} rateDate={data.usd_rate_date} size="text-lg" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button to={`/seller/builds/${b.id}`} variant="secondary" size="sm"><Pencil className="size-4" aria-hidden />{t('sellerBuilds.edit')}</Button>
              <Button variant="secondary" size="sm" onClick={() => setSale(b, !b.is_in_stock)}>{t(b.is_in_stock ? 'sellerBuilds.takeOff' : 'sellerBuilds.putBack')}</Button>
              {b.is_in_stock && <Button href={storeUrl(`/builds/${b.id}`)} target="_blank" rel="noreferrer" variant="text" size="sm"><ExternalLink className="size-4" aria-hidden />{t('seller.openStore')}</Button>}
              <Button variant="text" size="sm" className="!text-danger" onClick={() => setRemoving(b)}><Trash2 className="size-4" aria-hidden />{t('sellerBuilds.delete')}</Button>
            </div>
          </Card>
        ))}
      </ul>
      <Modal open={Boolean(removing)} onClose={() => setRemoving(null)} title={t('sellerBuilds.deleteTitle')}
        footer={<><Button variant="secondary" onClick={() => setRemoving(null)}>{t('sellerBuilds.cancel')}</Button><Button variant="danger" onClick={remove}>{t('sellerBuilds.delete')}</Button></>}>
        <p className="text-sm">{t('sellerBuilds.deleteText', { name: removing?.name })}</p>
      </Modal>
    </div>
  )
}

// "Paste as text": the post -> a draft by slots in the editor (nothing is saved before "Publish").
// Phase 17.2: code first (instant), then one AI request only for the parts the code did not read, with progress;
// "Don't wait" or an AI failure shows what the code read
function PasteBox({ onParsed }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')
  const pending = useRef(null)
  const finish = (draft) => {
    pending.current = null
    setBusy(false)
    setProgress(null)
    onParsed(draft, text)
  }
  const parse = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const rules = (await api.post('/seller/builds/parse', { text, ai: false })).data
      if (!rules.ai_pending) return finish(rules)
      const ticket = {}
      pending.current = { ticket, rules }
      setProgress({ done: rules.parts_total - rules.ai_pending, total: rules.parts_total })
      let draft = { ...rules, ai: 'failed' }
      try {
        draft = (await api.post('/seller/builds/parse', { text, ai: true })).data
      } catch { /* the AI step failed: the draft keeps what the code read */ }
      if (pending.current?.ticket === ticket) finish(draft)
    } catch (err) {
      const code = err.response?.data?.detail?.code
      setError(code ? t(`sellerBuilds.error.${code}`, { defaultValue: t(errorKey(err)) }) : t(errorKey(err)))
      setBusy(false)
      setProgress(null)
    }
  }
  const skip = () => pending.current && finish({ ...pending.current.rules, ai: 'skipped' })
  return (
    <Card as="form" onSubmit={parse} className="grid gap-3">
      <h2 className="text-h3">{t('sellerBuilds.textTitle')}</h2>
      <p className="text-sm text-muted">{t('sellerBuilds.textHint')}</p>
      <textarea rows={6} required minLength={3} className={inputClass} placeholder={t('sellerBuilds.textPlaceholder')}
        aria-label={t('sellerBuilds.textTitle')} value={text} onChange={(e) => setText(e.target.value)} />
      <ErrorText>{error}</ErrorText>
      {progress ? (
        <div className="grid gap-2" role="status">
          <p className="flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
            {t('sellerBuilds.progress', progress)}
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
          </div>
          <Button type="button" variant="text" size="sm" className="justify-self-start" onClick={skip}>{t('sellerBuilds.noWait')}</Button>
        </div>
      ) : (
        <Button type="submit" disabled={busy} className="justify-self-start">{busy ? t('sellerBuilds.parsing') : t('sellerBuilds.parse')}</Button>
      )}
    </Card>
  )
}

const draftToInitial = (draft, text) => ({
  ...draft, price: draft.price ?? '', text, parts: draft.components.map((c, i) => toEditorPart(c, `d${i}`)),
})

export function SellerBuildEditPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { defaultCurrency } = useOutletContext()
  const [method, setMethod] = useState(params.get('method') === 'text' ? 'text' : 'form')
  const [initial, setInitial] = useState(id ? undefined : null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.get(`/seller/builds/${id}`)
      .then((res) => setInitial({ ...res.data, parts: res.data.components.map((c) => toEditorPart(c, `c${c.id}`)) }))
      .catch((err) => setError(t(errorKey(err))))
  }, [id, t])

  const saved = () => {
    toast(t('sellerBuilds.saved'))
    navigate('/seller/builds')
  }
  const cancel = () => navigate('/seller/builds')

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <h1 className="text-h2 md:text-h1">{t(id ? 'sellerBuilds.editTitle' : 'sellerBuilds.newTitle')}</h1>
      <ErrorText>{error}</ErrorText>
      {!id && (
        <Tabs label={t('sellerBuilds.add')} value={method} onChange={(m) => { setMethod(m); setInitial(null) }}
          tabs={[{ value: 'form', label: t('sellerBuilds.byForm') }, { value: 'text', label: t('sellerBuilds.byText') }]} />
      )}
      {!id && <TrustHint />}
      {id && initial === undefined && !error && <Skeleton className="h-64 w-full rounded-xl" />}
      {!id && method === 'text' && !initial && <PasteBox onParsed={(draft, text) => setInitial(draftToInitial(draft, text))} />}
      {!id && method === 'text' && initial && (
        <div className="rounded-md bg-surface-2 p-3 text-sm">
          <p>{t('sellerBuilds.parsed')}</p>
          {initial.ai_pending > 0 && initial.ai !== 'done' && <p className="mt-1 text-muted">{t('sellerBuilds.aiMissed', { count: initial.ai_pending })}</p>}
        </div>
      )}
      {(id ? initial : method === 'form' || initial) && (
        <BuildEditor key={initial ? 'draft' : 'empty'} initial={initial} buildId={id} defaultCurrency={defaultCurrency}
          onSaved={saved} onCancel={cancel} />
      )}
      {/* Phase 14: photos of a saved build (a new one gets them after "Опубликовать") */}
      {id && initial && (
        <Card>
          <h2 className="mb-3 text-h3">{t('photo.build')}</h2>
          <PhotoUploader ownerType="build" ownerId={Number(id)} hint={t('photo.buildHint')} />
        </Card>
      )}
    </div>
  )
}
