// Phase 13: the admin's moderation sections — stores, chat reports, disputed flags, card fixes, barcode conflicts and
// Telegram channels. Every action asks for a comment (a reason where someone is blocked or refused) and is journaled.
import { ArrowRight, Ellipsis, ExternalLink, ShieldOff } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import Flags from '../components/Flags'
import { Dropdown, DropdownItem, useToast } from '../components/overlays'
import { Badge, Button, Card, Input, Select, Tabs } from '../components/ui'
import { STORE_CITIES } from '../config/cities'
import { storeUrl } from '../config/sites'
import api from '../services/api'
import { adminErrorKey, dateTime, useAdminData } from '../services/admin'
import { formatPrice } from '../services/format'
import { systemText } from '../services/reservations'
import { ActionModal, ChannelState, Loading, LogLine, PageTitle, adminChanged } from './AdminPage'

const productLink = (id) => storeUrl(`/products/${id}`)

function Ext({ to, children }) {
  return (
    <a href={to} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium break-words text-primary hover:underline">
      {children}<ExternalLink className="size-3.5 shrink-0" aria-hidden />
    </a>
  )
}

function YesNo({ label, value, onChange, yes, no }) {
  const { t } = useTranslation()
  return (
    <Select label={label} value={value} onChange={onChange}>
      <option value="">{t('admin.all')}</option>
      <option value="true">{yes}</option>
      <option value="false">{no}</option>
    </Select>
  )
}

function StoreBadges({ s }) {
  const { t } = useTranslation()
  return (
    <span className="flex flex-wrap gap-1">
      <Badge tone={s.is_verified ? 'success' : 'warning'}>{t(s.is_verified ? 'admin.stores.verifiedBadge' : 'admin.stores.unverifiedBadge')}</Badge>
      {s.is_demo && <Badge>{t('admin.demo')}</Badge>}
      <Badge tone="info">{t(`admin.stores.mode_${s.stock_mode}`)}</Badge>
      {s.blocked && <Badge tone="danger">{t('admin.stores.blockedBadge')}</Badge>}
    </span>
  )
}

// --- stores -----------------------------------------------------------------------------------------------------------

export function AdminStores() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const [f, setF] = useState({ q: '', city: '', verified: params.get('verified') || '', demo: '', mode: '', blocked: '' })
  const [data] = useAdminData('/admin/stores', f)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  return (
    <>
      <PageTitle title={t('admin.stores.title')} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Input label={t('admin.stores.search')} type="search" value={f.q} onChange={set('q')} className="col-span-2 md:col-span-1" />
        <Select label={t('admin.stores.city')} value={f.city} onChange={set('city')}>
          <option value="">{t('admin.all')}</option>
          {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
        </Select>
        <YesNo label={t('admin.stores.verified')} value={f.verified} onChange={set('verified')} yes={t('admin.stores.verifiedYes')} no={t('admin.stores.verifiedNo')} />
        <YesNo label={t('admin.stores.kind')} value={f.demo} onChange={set('demo')} yes={t('admin.stores.demoYes')} no={t('admin.stores.demoNo')} />
        <Select label={t('admin.stores.mode')} value={f.mode} onChange={set('mode')}>
          <option value="">{t('admin.all')}</option>
          <option value="price">{t('admin.stores.mode_price')}</option>
          <option value="stock">{t('admin.stores.mode_stock')}</option>
        </Select>
        <YesNo label={t('admin.stores.blocked')} value={f.blocked} onChange={set('blocked')} yes={t('admin.stores.blockedYes')} no={t('admin.stores.blockedNo')} />
      </div>
      <Loading data={data}>
        <ul className="grid gap-2">
          {data?.map((s) => (
            <li key={s.id}>
              <Link to={`/admin/stores/${s.id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-surface p-4 shadow-card outline-none hover:border-primary focus-visible:ring-2 focus-visible:ring-primary">
                <span className="min-w-0">
                  <span className="block font-semibold break-words">{s.name}</span>
                  <span className="block text-xs text-muted">{s.cities.map((c) => t(`cities.${c}`)).join(', ')} · {t('admin.stores.goods', { count: s.goods })}</span>
                </span>
                <StoreBadges s={s} />
              </Link>
            </li>
          ))}
        </ul>
      </Loading>
    </>
  )
}

export function AdminStoreCard() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [s, reload] = useAdminData(`/admin/stores/${id}`)
  const [action, setAction] = useState(null)
  const verify = (verified) => setAction({
    title: t(verified ? 'admin.stores.verify' : 'admin.stores.unverify'),
    onConfirm: async (comment) => { await api.post(`/admin/stores/${id}/verify`, { verified, comment }); reload() },
  })
  const block = (blocked) => setAction({
    title: t(blocked ? 'admin.stores.block' : 'admin.stores.unblock'), danger: blocked, required: blocked,
    hint: blocked ? t('admin.stores.blockHint') : null, fieldHint: blocked ? t('admin.reasonHint') : null,
    field: blocked ? undefined : false,
    onConfirm: async (reason) => { await api.post(`/admin/stores/${id}/block`, { blocked, reason }); reload() },
  })
  return (
    <Loading data={s}>
      {s && (
        <div className="grid gap-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <Link to="/admin/stores" className="text-sm text-muted hover:underline">← {t('admin.stores.title')}</Link>
              <h1 className="mt-1 text-h1 break-words">{s.name}</h1>
              <div className="mt-2"><StoreBadges s={s} /></div>
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <Button variant="secondary" className="w-full sm:w-auto" onClick={() => verify(!s.is_verified)}>{t(s.is_verified ? 'admin.stores.unverify' : 'admin.stores.verify')}</Button>
              <Button variant={s.blocked ? 'secondary' : 'danger'} className="w-full sm:w-auto" onClick={() => block(!s.blocked)}>{t(s.blocked ? 'admin.stores.unblock' : 'admin.stores.block')}</Button>
            </div>
          </div>
          {s.blocked && <p className="rounded-lg border border-danger-line bg-danger-soft p-3 text-sm text-danger">{t('admin.stores.blockReason', { reason: s.block_reason })}</p>}
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <h2 className="mb-2 text-h3">{t('admin.stores.profile')}</h2>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-muted">{t('admin.stores.owner')}</dt><dd className="break-all">{s.email}</dd>
                <dt className="text-muted">{t('admin.stores.stir')}</dt><dd>{s.inn_stir || '—'}</dd>
                <dt className="text-muted">{t('admin.stores.phone')}</dt><dd>{s.phone || '—'}</dd>
              </dl>
              <p className="mt-3 text-sm">{t('admin.stores.goods', { count: s.goods })} · {t('admin.stores.builds', { count: s.builds })}</p>
              <p className="mt-1 text-sm">{t('admin.stores.flags')}: {['active', 'disputed', 'dismissed'].map((k) => `${t(`admin.stores.flagStatus.${k}`)} ${s.flags[k] || 0}`).join(', ')}</p>
              <p className="mt-3 text-xs text-muted">{t('admin.stores.privacy')}</p>
            </Card>
            <Card>
              <h2 className="mb-2 text-h3">{t('admin.stores.branches')}</h2>
              <ul className="grid gap-2 text-sm">
                {s.branches.map((b) => (
                  <li key={b.id}>
                    <span className="font-medium">{t(`cities.${b.city}`)}{b.name && ` · ${b.name}`}</span>
                    {b.is_main && <Badge className="ml-1">{t('admin.stores.main')}</Badge>}
                    <span className="block break-words text-muted">{b.address}{b.landmark && `, ${b.landmark}`}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
          <Card>
            <h2 className="mb-2 text-h3">{t('admin.stores.reports')}</h2>
            {s.reports.length ? <ul className="grid gap-1 text-sm">{s.reports.map((r) => (
              <li key={r.id}><Link to={`/admin/reports?id=${r.id}`} className="text-primary hover:underline">#{r.id} · {t(`chat.reason.${r.reason}`, r.reason)}</Link> — {t(`admin.reports.status.${r.status}`)}</li>
            ))}</ul> : <p className="text-sm text-muted">{t('admin.empty')}</p>}
          </Card>
          <Card>
            <h2 className="mb-1 text-h3">{t('admin.stores.history')}</h2>
            {s.history.length ? <ul>{s.history.map((a) => <LogLine key={a.id} a={a} />)}</ul> : <p className="text-sm text-muted">{t('admin.log.empty')}</p>}
          </Card>
          <ActionModal action={action} onClose={() => setAction(null)} />
        </div>
      )}
    </Loading>
  )
}

// --- chat reports -----------------------------------------------------------------------------------------------------

// One side of a report: "Магазин Silicon Plus" or "Покупатель buyer1@…", marked if already blocked
function Party({ side, r }) {
  const { t } = useTranslation()
  const who = side === 'store' ? r.store : r.buyer
  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-1">
      <span className="text-muted">{t(side === 'store' ? 'admin.reports.store' : 'admin.reports.buyer')}</span>
      {side === 'store'
        ? <Link className="font-medium text-primary hover:underline" to={`/admin/stores/${who?.id}`}>{who?.name}</Link>
        : <span className="font-medium break-all">{who?.email}</span>}
      {who?.blocked && <Badge tone="danger">{t('admin.users.blockedBadge')}</Badge>}
    </span>
  )
}

// A reservation status line is a thin grey divider; people's lines are messages
function ReportMessage({ m }) {
  const { t } = useTranslation()
  if (m.author === 'system') {
    return (
      <li className="flex items-center gap-2 py-0.5 text-xs text-faint">
        <span aria-hidden className="h-px min-w-4 flex-1 bg-line-strong" />
        <span className="max-w-[80%] text-center">{systemText(t, m)} · {dateTime(m.at)}</span>
        <span aria-hidden className="h-px min-w-4 flex-1 bg-line-strong" />
      </li>
    )
  }
  return (
    <li className={`max-w-[85%] rounded-lg px-3 py-2 text-sm shadow-card ${m.author === 'store' ? 'justify-self-end bg-primary-soft' : 'justify-self-start bg-surface'}`}>
      <span className="block text-xs text-muted">{t(`admin.reports.author.${m.author}`)} · {dateTime(m.at)}</span>
      <span className="break-words whitespace-pre-wrap">{m.text}</span>
    </li>
  )
}

export const BLOCK_ACTION = { buyer: 'block_user', store: 'block_store' }
const BLOCK_LABEL = { buyer: 'admin.reports.blockBuyer', store: 'admin.reports.blockStore' }

// Who complained about whom: the store complained -> the main action blocks the buyer, and the other way round
export function reportSides(r) {
  const from = r.reporter_side === 'store' ? 'store' : 'buyer'
  return { from, target: from === 'store' ? 'buyer' : 'store' }
}

function ReportDetail({ id, onChanged }) {
  const { t } = useTranslation()
  const [r, reload] = useAdminData(`/admin/reports/${id}`)
  const [action, setAction] = useState(null)
  const act = (kind) => setAction({
    title: t({ dismiss: 'admin.reports.dismiss', block_user: BLOCK_LABEL.buyer, block_store: BLOCK_LABEL.store }[kind]),
    // Any block goes through a confirmation with a required reason (the blocked side sees it)
    danger: kind !== 'dismiss', required: kind !== 'dismiss', fieldHint: kind !== 'dismiss' ? t('admin.reasonHint') : null,
    hint: kind === 'block_user' ? t('admin.reports.blockUserHint') : kind === 'block_store' ? t('admin.stores.blockHint') : null,
    onConfirm: async (comment) => { await api.post(`/admin/reports/${id}`, { action: kind, comment }); reload(); onChanged() },
  })
  if (!r) return <Loading data={r} />
  const { from, target } = reportSides(r)
  const blocked = (side) => (side === 'store' ? r.store : r.buyer)?.blocked
  return (
    <Card className="grid gap-4">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold">{t(`chat.reason.${r.reason}`, r.reason)}</span>
        <span className="inline-flex items-center gap-2"><span aria-hidden className="text-faint">·</span>
          <Badge tone={r.status === 'new' ? 'warning' : 'neutral'}>{t(`admin.reports.status.${r.status}`)}</Badge></span>
        <span className="inline-flex items-center gap-2 text-sm whitespace-nowrap text-muted"><span aria-hidden className="text-faint">·</span>
          {dateTime(r.created_at)}</span>
      </p>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" title={t('admin.reports.whoWhom')}>
        <Party side={from} r={r} />
        <span className="inline-flex min-w-0 items-center gap-2">
          <ArrowRight className="size-4 shrink-0 text-faint" aria-label={t('admin.reports.about')} />
          <Party side={target} r={r} />
        </span>
      </p>
      {r.comment && (
        <blockquote className="border-l-4 border-line-strong pl-3 text-sm break-words italic">«{r.comment}»</blockquote>
      )}
      <section>
        <h3 className="text-sm font-semibold">{t('admin.reports.conversation')}</h3>
        <p className="text-xs text-muted">{t('admin.reports.onlyThis')}</p>
        <ul className="mt-2 grid max-h-96 gap-2 overflow-y-auto rounded-lg bg-surface-2 p-3">
          {r.messages.map((m) => <ReportMessage key={m.id} m={m} />)}
        </ul>
      </section>
      {r.status === 'new' ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button variant="danger" className="w-full sm:w-auto" disabled={blocked(target)} onClick={() => act(BLOCK_ACTION[target])}>
            {t(BLOCK_LABEL[target])}
          </Button>
          <Button variant="secondary" className="w-full sm:w-auto" onClick={() => act('dismiss')}>{t('admin.reports.dismiss')}</Button>
          <div className="w-full sm:w-auto">
            <Dropdown align="left" up trigger={({ open, toggle }) => (
              <Button variant="secondary" className="w-full sm:w-auto" onClick={toggle} aria-expanded={open}
                aria-label={t('admin.reports.more')} title={t('admin.reports.more')}>
                <Ellipsis className="size-5" aria-hidden /><span className="sm:hidden">{t('admin.reports.moreShort')}</span>
              </Button>
            )}>
              <DropdownItem icon={ShieldOff} disabled={blocked(from)} onClick={() => act(BLOCK_ACTION[from])}>
                {t(BLOCK_LABEL[from])}
              </DropdownItem>
            </Dropdown>
          </div>
        </div>
      ) : (
        <p className="text-sm">
          <Badge tone="success">{t(`admin.reports.resolution.${r.resolution}`)}</Badge>
          {r.admin_comment && <span className="ml-2 break-words text-muted">{t('admin.reports.adminComment', { text: r.admin_comment })}</span>}
        </p>
      )}
      <ActionModal action={action} onClose={() => setAction(null)} />
    </Card>
  )
}

export function AdminReports() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [data, reload] = useAdminData('/admin/reports')
  const open = params.get('id')
  return (
    <>
      <PageTitle title={t('admin.reports.title')} />
      <Loading data={data}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ul className="grid content-start gap-2">
            {data?.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => setParams({ id: r.id })}
                  className={`w-full rounded-xl border bg-surface p-3 text-left shadow-card outline-none focus-visible:ring-2 focus-visible:ring-primary ${String(r.id) === open ? 'border-primary' : 'border-line hover:border-faint'}`}>
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">#{r.id} · {t(`chat.reason.${r.reason}`, r.reason)}</span>
                    <Badge tone={r.status === 'new' ? 'warning' : 'neutral'}>{t(`admin.reports.status.${r.status}`)}</Badge>
                  </span>
                  <span className="block text-xs break-words text-muted">{r.store?.name} · {dateTime(r.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
          {open && <ReportDetail key={open} id={open} onChanged={reload} />}
        </div>
      </Loading>
    </>
  )
}

// --- disputed flags ---------------------------------------------------------------------------------------------------

export function AdminFlags() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('disputed')
  const [data, reload] = useAdminData('/admin/flags', { status: tab })
  const [action, setAction] = useState(null)
  const decide = (f, decision) => setAction({
    title: t(decision === 'upheld' ? 'admin.flags.upheld' : 'admin.flags.dismiss'), required: decision === 'upheld',
    label: decision === 'upheld' ? t('admin.flags.answer') : t('admin.commentOptional'),
    fieldHint: decision === 'upheld' ? t('admin.flags.answerHint') : null,
    hint: decision === 'dismissed' ? t('admin.flags.dismissHint') : null,
    onConfirm: async (answer) => { await api.post(`/admin/flags/${f.id}`, { decision, answer }); reload() },
  })
  return (
    <>
      <PageTitle title={t('admin.flags.title')}>
        <Tabs value={tab} onChange={setTab} tabs={['disputed', 'done'].map((v) => ({ value: v, label: t(`admin.flags.tabs.${v}`) }))} />
      </PageTitle>
      <Loading data={data}>
        <ul className="grid gap-3">
          {data?.map((f) => (
            <li key={f.id}>
              <Card className="grid gap-2">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Ext to={productLink(f.product.id)}>{f.product.name}</Ext>
                  <span className="text-sm text-muted"><Link to={`/admin/stores/${f.store.id}`} className="hover:underline">{f.store.name}</Link> · {formatPrice(f.offer.price, f.offer.currency)}</span>
                </div>
                <p className="text-sm"><span className="text-muted">{t('admin.flags.raw')}: </span><span className="break-words">{f.offer.raw_name}</span></p>
                <Flags flags={[f]} className="grid gap-1" />
                {f.dispute_comment && <p className="rounded-md bg-surface-2 p-2 text-sm break-words"><span className="text-muted">{t('admin.flags.sellerComment')}: </span>{f.dispute_comment}</p>}
                {f.status === 'disputed' ? (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => decide(f, 'upheld')}>{t('admin.flags.upheld')}</Button>
                    <Button onClick={() => decide(f, 'dismissed')}>{t('admin.flags.dismiss')}</Button>
                  </div>
                ) : (
                  <p className="text-sm"><Badge tone={f.resolution === 'dismissed' ? 'success' : 'warning'}>{t(`admin.flags.resolution.${f.resolution}`)}</Badge>
                    {f.admin_answer && <span className="ml-2 break-words text-muted">{f.admin_answer}</span>}</p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </Loading>
      <ActionModal action={action} onClose={() => setAction(null)} />
    </>
  )
}

// --- card fixes -------------------------------------------------------------------------------------------------------

const FIX_FIELDS = ['name', 'brand', 'model', 'category']

function FixCompare({ fix }) {
  const { t } = useTranslation()
  const show = (side, k) => (k === 'category' && side?.[k] ? t(`categories.${side[k]}`) : side?.[k]) || '—'
  const specs = (side) => Object.entries(side?.specs || {}).map(([k, v]) => `${t(`specs.${k}`, k)}: ${v}`).join(', ') || '—'
  return (
    <div className="grid gap-1 text-sm">
      {[...FIX_FIELDS, 'specs'].map((k) => {
        const before = k === 'specs' ? specs(fix.before) : show(fix.before, k)
        const after = k === 'specs' ? specs(fix.after) : show(fix.after, k)
        return (
          <div key={k} className="grid gap-x-2 sm:grid-cols-[8rem_minmax(0,1fr)_auto_minmax(0,1fr)]">
            <span className="text-muted">{t(`admin.fixes.field.${k}`)}</span>
            <span className="break-words">{before}</span>
            <ArrowRight className="hidden size-4 text-faint sm:block" aria-hidden />
            <span className={`break-words ${before !== after ? 'font-semibold text-primary' : ''}`}>{after}</span>
          </div>
        )
      })}
    </div>
  )
}

export function AdminFixes() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('pending')
  const [data, reload] = useAdminData('/admin/fixes', { status: tab })
  const [action, setAction] = useState(null)
  const accept = (fix) => setAction({
    title: t(fix.merge ? 'admin.fixes.acceptMerge' : 'admin.fixes.accept'),
    hint: fix.merge ? `${t('admin.fixes.mergeInto', { name: fix.merge.target.name })}. ${t('admin.fixes.mergeItems', fix.merge)}` : null,
    done: t(fix.merge ? 'admin.fixes.merged' : 'admin.fixes.applied'),
    onConfirm: async (comment) => { await api.post(`/admin/fixes/${fix.id}/accept`, { comment }); reload() },
  })
  const reject = (fix) => setAction({
    title: t('admin.fixes.reject'), required: true, label: t('admin.fixes.rejectReason'), danger: true,
    onConfirm: async (reason) => { await api.post(`/admin/fixes/${fix.id}/reject`, { reason }); reload() },
  })
  return (
    <>
      <PageTitle title={t('admin.fixes.title')}>
        <Tabs value={tab} onChange={setTab} tabs={['pending', 'done'].map((v) => ({ value: v, label: t(`admin.fixes.tabs.${v}`) }))} />
      </PageTitle>
      <Loading data={data}>
        <ul className="grid gap-3">
          {data?.map((fix) => (
            <li key={fix.id}>
              <Card className="grid gap-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  {fix.product ? <Ext to={productLink(fix.product.id)}>{fix.product.name}</Ext> : <span>—</span>}
                  <span className="text-sm text-muted">{t('admin.fixes.by', { store: fix.store?.name })} · {t('admin.fixes.selling', { count: fix.stores_selling })}</span>
                </div>
                <FixCompare fix={fix} />
                {fix.result && <p className="text-sm"><span className="text-muted">{t('admin.fixes.result')}: </span><span className="font-medium break-words">{fix.result.name}</span></p>}
                {fix.result_error && <p className="text-sm text-danger">{t('admin.fixes.resultError')} ({t(`admin.error.${fix.result_error}`)})</p>}
                {fix.merge && (
                  <div className="rounded-lg border border-warning-line bg-warning-soft p-3 text-sm text-warning">
                    <p className="font-semibold">{t('admin.fixes.merge')}</p>
                    <p>{t('admin.fixes.mergeInto', { name: fix.merge.target.name })}</p>
                    <p>{t('admin.fixes.mergeItems', fix.merge)}</p>
                  </div>
                )}
                {fix.status === 'pending' ? (
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => accept(fix)} disabled={!!fix.result_error}>{t(fix.merge ? 'admin.fixes.acceptMerge' : 'admin.fixes.accept')}</Button>
                    <Button variant="secondary" onClick={() => reject(fix)}>{t('admin.fixes.reject')}</Button>
                  </div>
                ) : (
                  <p className="text-sm"><Badge tone={fix.status === 'accepted' ? 'success' : 'neutral'}>{t(`admin.fixes.status.${fix.status}`)}</Badge>
                    {fix.merged_into && <span className="ml-2 text-muted">{t('admin.fixes.merged')}</span>}
                    {fix.reject_reason && <span className="ml-2 break-words text-muted">{fix.reject_reason}</span>}</p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </Loading>
      <ActionModal action={action} onClose={() => setAction(null)} />
    </>
  )
}

// --- barcodes ---------------------------------------------------------------------------------------------------------

function CodeCard({ c, onDecide }) {
  const { t } = useTranslation()
  return (
    <Card className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-lg font-semibold break-all">{c.code}</span>
        {c.status && <Badge tone={c.status === 'conflict' ? 'danger' : c.status === 'confirmed' ? 'success' : 'neutral'}>{t(`admin.barcodes.status.${c.status}`)}</Badge>}
      </div>
      {!c.cards.length && <p className="text-sm text-muted">{t('admin.barcodes.noBindings')}</p>}
      <ul className="grid gap-2">
        {c.cards.map((card) => (
          <li key={card.product_id} className={`grid gap-1 rounded-lg border p-3 ${c.product_id === card.product_id ? 'border-success-line bg-success-soft' : 'border-line'}`}>
            <Ext to={productLink(card.product_id)}>{card.name}</Ext>
            <span className="text-sm break-words text-muted">
              {card.stores.map((s) => `${s.name}${s.admin_status === 'disputed' ? ` (${t('admin.barcodes.disputed')})` : ''}`).join(', ')}
            </span>
            {onDecide && c.status === 'conflict' && (
              <Button size="sm" variant="secondary" className="justify-self-start" onClick={() => onDecide(c, card)}>{t('admin.barcodes.chooseThis')}</Button>
            )}
          </li>
        ))}
      </ul>
      {onDecide && c.status === 'conflict' && (
        <Button variant="danger" size="sm" className="justify-self-start" onClick={() => onDecide(c, null)}>{t('admin.barcodes.rejectAll')}</Button>
      )}
    </Card>
  )
}

export function AdminBarcodes() {
  const { t } = useTranslation()
  const [data, reload] = useAdminData('/admin/barcodes/conflicts')
  const [code, setCode] = useState('')
  const [found, setFound] = useState(null)
  const [error, setError] = useState(null)
  const [action, setAction] = useState(null)
  const lookup = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setFound((await api.get('/admin/barcodes/lookup', { params: { code } })).data)
    } catch (err) {
      setFound(null)
      setError(t(adminErrorKey(err)))
    }
  }
  const decide = (c, card) => setAction({
    title: card ? t('admin.barcodes.chooseThis') : t('admin.barcodes.rejectAll'), danger: !card,
    hint: card ? card.name : t('admin.barcodes.rejectAllHint'),
    onConfirm: async (comment) => {
      await api.post(`/admin/barcodes/${encodeURIComponent(c.code)}`, { product_id: card?.product_id ?? null, comment })
      reload()
      if (found?.code === c.code) setFound((await api.get('/admin/barcodes/lookup', { params: { code: c.code } })).data)
    },
  })
  return (
    <>
      <PageTitle title={t('admin.barcodes.title')} hint={t('admin.barcodes.hint')} />
      <form onSubmit={lookup} className="mb-5 flex flex-wrap items-end gap-2">
        <Input label={t('admin.barcodes.lookup')} placeholder={t('admin.barcodes.lookupPlaceholder')} value={code}
          onChange={(e) => setCode(e.target.value)} error={error} className="min-w-0 flex-1 basis-56" inputMode="numeric" />
        <Button type="submit" disabled={!code.trim()}>{t('admin.barcodes.find')}</Button>
      </form>
      {found && <div className="mb-5"><CodeCard c={found} onDecide={decide} /></div>}
      <Loading data={data} empty={t('admin.barcodes.noConflicts')}>
        <ul className="grid gap-3">{data?.map((c) => <li key={c.code}><CodeCard c={c} onDecide={decide} /></li>)}</ul>
      </Loading>
      <ActionModal action={action} onClose={() => setAction(null)} />
    </>
  )
}

// --- Telegram channels ------------------------------------------------------------------------------------------------

function AddChannel({ onAdded }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [f, setF] = useState({ username: '', title: '', city: 'tashkent' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/admin/channels', f)
      toast(t('admin.channels.added'))
      setF({ username: '', title: '', city: 'tashkent' })
      adminChanged()
      onAdded()
    } catch (err) {
      setError(t(adminErrorKey(err)))
    } finally {
      setBusy(false)
    }
  }
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  return (
    <Card as="form" onSubmit={submit} className="mb-5 grid gap-3">
      <h2 className="text-h3">{t('admin.channels.add')}</h2>
      <p className="-mt-2 text-sm text-muted">{t('admin.channels.addHint')}</p>
      <div className="grid gap-3 md:grid-cols-3">
        <Input label={t('admin.channels.username')} value={f.username} onChange={set('username')} placeholder="@channel" error={error} />
        <Input label={t('admin.channels.titleField')} value={f.title} onChange={set('title')} />
        <Select label={t('admin.channels.city')} value={f.city} onChange={set('city')}>
          {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
        </Select>
      </div>
      <Button type="submit" className="justify-self-start" disabled={busy || !f.username.trim()}>{t('admin.channels.add')}</Button>
    </Card>
  )
}

function ChannelRow({ ch, onChanged, onDelete }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const patch = async (body) => {
    try { await api.patch(`/admin/channels/${ch.id}`, body); onChanged() } catch (err) { toast(t(adminErrorKey(err)), 'danger') }
  }
  const fetchNow = async () => {
    setBusy(true)
    try { await api.post(`/admin/channels/${ch.id}/fetch`); onChanged() } catch (err) { toast(t(adminErrorKey(err)), 'danger') } finally { setBusy(false) }
  }
  const log = ch.last_log
  return (
    <Card className="grid gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Ext to={ch.url}>@{ch.username}</Ext>
          <p className="text-sm break-words text-muted">{ch.title}</p>
        </div>
        <Badge tone={ch.enabled ? 'success' : 'neutral'}>{t(ch.enabled ? 'admin.channels.enabled' : 'admin.channels.disabled')}</Badge>
      </div>
      <ChannelState ch={ch} />
      {log && (
        <div className="rounded-md bg-surface-2 p-2 text-xs text-muted">
          <p className="font-semibold text-ink">{t('admin.channels.log')} · {dateTime(log.at)}</p>
          <p>{t('admin.channels.logLine', log)}</p>
          {Object.keys(log.skipped || {}).length > 0 && <p>{t('admin.channels.skipped', { text: Object.entries(log.skipped).map(([k, v]) => `${k}: ${v}`).join(', ') })}</p>}
          {log.error && <p className="text-danger">{t('admin.channels.error', { text: log.error })}</p>}
        </div>
      )}
      <div className="grid gap-2 sm:flex sm:flex-wrap sm:items-end">
        <Select label={t('admin.channels.city')} value={ch.city} onChange={(e) => patch({ city: e.target.value })} className="sm:w-40">
          {STORE_CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
        </Select>
        <Button variant="secondary" onClick={() => patch({ enabled: !ch.enabled })}>{t(ch.enabled ? 'admin.channels.disable' : 'admin.channels.enable')}</Button>
        <Button onClick={fetchNow} disabled={busy || !ch.enabled} title={t('admin.channels.fetchHint')}>{busy ? t('admin.channels.fetching') : t('admin.channels.fetch')}</Button>
        <Button variant="danger" onClick={() => onDelete(ch)}>{t('admin.channels.delete')}</Button>
      </div>
    </Card>
  )
}

export function AdminChannels() {
  const { t } = useTranslation()
  const [data, reload] = useAdminData('/admin/channels')
  const [action, setAction] = useState(null)
  const remove = (ch) => setAction({
    title: `${t('admin.channels.delete')} @${ch.username}`, danger: true, hint: t('admin.channels.deleteHint'), field: false,
    done: t('admin.channels.deleted'),
    onConfirm: async () => { await api.delete(`/admin/channels/${ch.id}`); reload() },
  })
  return (
    <>
      <PageTitle title={t('admin.channels.title')} hint={t('admin.channels.fetchHint')} />
      <AddChannel onAdded={reload} />
      <Loading data={data}>
        <ul className="grid gap-3">{data?.map((ch) => <li key={ch.id}><ChannelRow ch={ch} onChanged={reload} onDelete={remove} /></li>)}</ul>
      </Loading>
      <ActionModal action={action} onClose={() => setAction(null)} />
    </>
  )
}
