// Phase 13: the admin panel — the third interface on the Workspace frame (after the storefront and the cabinet).
// Its own top bar "ALT STORES · администрирование", the sections on the left, tabs on a phone, its own login.
import {
  Barcode, BookOpenText, Flag, LayoutDashboard, LogOut, MessageSquareWarning, PencilLine, Send, ShieldAlert, Store, Users,
} from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, SubmitButton, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Modal, useToast } from '../components/overlays'
import { Badge, Button, Card, EmptyState, FieldBox, Input, PasswordInput, Select, Skeleton, inputClass } from '../components/ui'
import { storeUrl } from '../config/sites'
import Workspace from '../layouts/Workspace'
import { NotificationBell } from '../components/Notifications'
import api, { errorKey } from '../services/api'
import { LOG_GROUPS, actionGroup, adminErrorKey, dateTime, useAdminData } from '../services/admin'
import { useAuth } from '../services/auth.jsx'
import { formatDate } from '../services/format'
import { returnTo } from '../services/roles'

// `tab`: in the phone bar (six fit 360 px); the rest open from the overview's list of sections
export const ADMIN_SECTIONS = [
  { to: '/admin', key: 'overview', icon: LayoutDashboard, end: true, tab: true },
  { to: '/admin/stores', key: 'stores', icon: Store, tab: true },
  { to: '/admin/reports', key: 'reports', icon: MessageSquareWarning, tab: true },
  { to: '/admin/flags', key: 'flags', icon: Flag, tab: true },
  { to: '/admin/fixes', key: 'fixes', icon: PencilLine, tab: true },
  { to: '/admin/barcodes', key: 'barcodes', icon: Barcode },
  { to: '/admin/channels', key: 'channels', icon: Send, tab: true },
  { to: '/admin/users', key: 'users', icon: Users },
  { to: '/admin/log', key: 'log', icon: BookOpenText },
]

function AdminFrame({ sections, children }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <Workspace home="/admin" subtitle={t('admin.subtitle')} sections={sections} navKey="admin.nav" tabKey="admin.tab"
      menuLabel={t('admin.menu')} sideTitle={user?.role === 'admin' ? user.email : null}
      actions={user?.role === 'admin' && (<>
        <NotificationBell allPath="/admin/notifications" />
        <Button variant="secondary" size="sm" onClick={() => { logout(); navigate('/admin/login') }}
          aria-label={t('admin.logout')} title={user.email} className="shrink-0 max-sm:!px-2.5">
          <LogOut className="size-4" aria-hidden /><span className="hidden sm:inline">{t('admin.logout')}</span>
        </Button>
      </>)}>
      {children}
    </Workspace>
  )
}

// Menu badges: how many wait for a decision; refreshed when a section changes something (event "admin:changed")
function useCounts() {
  const [counts, setCounts] = useState({})
  useEffect(() => {
    const load = () => api.get('/admin/counts').then((res) => setCounts(res.data)).catch(() => {})
    load()
    window.addEventListener('admin:changed', load)
    return () => window.removeEventListener('admin:changed', load)
  }, [])
  return counts
}

export const adminChanged = () => window.dispatchEvent(new Event('admin:changed'))

export default function AdminLayout() {
  const counts = useCounts()
  const sections = ADMIN_SECTIONS.map((s) => (counts[s.key] ? { ...s, badge: counts[s.key] } : s))
  return <AdminFrame sections={sections}><Outlet /></AdminFrame>
}

export function AdminAuthLayout() {
  return <AdminFrame><Outlet /></AdminFrame>
}

// A seller or a buyer opened /admin/...
export function NoAccessPage() {
  const { t } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  return (
    <AdminFrame>
      <Card className="mx-auto max-w-md text-center md:mt-4 md:!p-8">
        <ShieldAlert className="mx-auto size-10 text-danger" aria-hidden />
        <h1 className="mt-4 text-h1">{t('admin.noAccessTitle')}</h1>
        <p className="mt-2 text-sm text-muted">{t('admin.noAccessText')}</p>
        <div className="mt-6 grid gap-2">
          <Button size="lg" onClick={() => { logout(); navigate('/admin/login') }}>{t('admin.loginAsAdmin')}</Button>
          <Button size="lg" variant="secondary" href={storeUrl('/')}>{t('admin.backToStore')}</Button>
        </div>
      </Card>
    </AdminFrame>
  )
}

export function AdminLoginPage() {
  const { t } = useTranslation()
  const { adminLogin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = {}
    const emailError = emailErrorKey(email)
    if (emailError) found.email = t(emailError)
    if (!password) found.password = t('errors.required')
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const user = await adminLogin(email, password)
      navigate(returnTo(user, location.state?.from), { replace: true })
    } catch (err) {
      const key = errorKey(err)
      const detail = err.response?.data?.detail
      setErrors({ [fieldOfError(key)]: t(key, typeof detail === 'object' ? detail : {}) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t('admin.loginTitle')} hint={t('admin.loginHint')}>
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <Input label={t('auth.email')} type="email" autoComplete="username" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label={t('auth.password')} autoComplete="current-password" error={errors.password}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="mt-1">
          <ErrorText>{errors.form}</ErrorText>
          <SubmitButton busy={busy} busyText={t('auth.loading')}>{t('auth.submitLogin')}</SubmitButton>
        </div>
      </form>
    </AuthCard>
  )
}

// --- shared pieces of the sections ------------------------------------------------------------------------------------

export function PageTitle({ title, hint, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-h1">{title}</h1>
        {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
      </div>
      {children}
    </div>
  )
}

export function Loading({ data, children, empty }) {
  const { t } = useTranslation()
  if (data === undefined) return <Skeleton className="h-48 w-full rounded-xl" />
  if (data === null) return <p className="text-sm text-danger">{t('errors.unknown')}</p>
  if (Array.isArray(data) && !data.length) return <EmptyState title={empty || t('admin.empty')} />
  return children
}

export function TextArea({ label, hint, error, ...props }) {
  const id = useId()
  return (
    <FieldBox label={label} hint={hint} error={error} id={id}>
      <textarea id={id} rows={3} className={`${inputClass} resize-y`} {...props} />
    </FieldBox>
  )
}

// An action with a comment: `required` — a reason / an answer must be written. onConfirm(text) may throw an axios
// error: its text is shown in the dialog
export function ActionModal({ action, onClose }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setText(''); setError(null) }, [action])
  if (!action) return null
  const submit = async () => {
    if (action.required && !text.trim()) { setError(t('admin.error.reason_required')); return }
    setBusy(true)
    try {
      await action.onConfirm(text.trim())
      toast(action.done || t('admin.done'))
      adminChanged()
      onClose()
    } catch (err) {
      setError(t(adminErrorKey(err)))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal open onClose={onClose} title={action.title} footer={<>
      <Button variant="secondary" onClick={onClose}>{t('admin.cancel')}</Button>
      <Button variant={action.danger ? 'danger' : 'primary'} onClick={submit} disabled={busy}>{action.confirm || action.title}</Button>
    </>}>
      {action.hint && <p className="mb-3 text-sm text-muted">{action.hint}</p>}
      {action.field !== false && (
        <TextArea label={action.label || (action.required ? t('admin.reason') : t('admin.commentOptional'))}
          hint={action.fieldHint} value={text} onChange={(e) => setText(e.target.value)} maxLength={300} error={error} />
      )}
      {action.field === false && error && <p className="text-sm text-danger">{error}</p>}
    </Modal>
  )
}

// --- overview ---------------------------------------------------------------------------------------------------------

const WAITING = [['stores', '/admin/stores?verified=false'], ['reports', '/admin/reports'], ['flags', '/admin/flags'],
  ['fixes', '/admin/fixes'], ['barcodes', '/admin/barcodes']]

export function ChannelState({ ch }) {
  const { t } = useTranslation()
  return (
    <span className="text-xs text-muted">
      {ch.checked_at ? t('admin.channels.lastRun', { date: dateTime(ch.checked_at) }) : t('admin.channels.never')}
      {' · '}{t('admin.channels.ads', { count: ch.ads })}
      {ch.last_error && <span className="block text-danger">{t('admin.channels.error', { text: ch.last_error })}</span>}
    </span>
  )
}

export function LogLine({ a }) {
  const { t } = useTranslation()
  return (
    <li className="grid gap-0.5 border-b border-line py-2.5 text-sm last:border-0">
      <span className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium">{t(`admin.action.${a.action}`)}</span>
        {a.title && <span className="min-w-0 break-words text-muted">«{a.title}»</span>}
      </span>
      {a.comment && <span className="break-words text-muted">{a.comment}</span>}
      <span className="text-xs text-faint">{dateTime(a.at)} · {a.admin}</span>
    </li>
  )
}

export function AdminOverview() {
  const { t } = useTranslation()
  const [data] = useAdminData('/admin/overview')
  return (
    <>
      <PageTitle title={t('admin.overview.title')} />
      <Loading data={data}>
        {data && (
          <div className="grid gap-6">
            <section>
              <h2 className="mb-3 text-h3">{t('admin.overview.waiting')}</h2>
              <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
                {WAITING.map(([key, to]) => (
                  <li key={key}>
                    <Link to={to} className="flex h-full flex-col justify-between gap-2 rounded-xl border border-line bg-surface p-4 shadow-card outline-none hover:border-primary focus-visible:ring-2 focus-visible:ring-primary">
                      <span className="text-sm text-muted">{t(`admin.overview.w.${key}`)}</span>
                      <span className={`text-2xl font-bold ${data.waiting[key] ? 'text-primary' : 'text-faint'}`}>{data.waiting[key]}</span>
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-sm text-muted">
                {t('admin.overview.users', { count: data.users })} · {t('admin.overview.blockedUsers', { count: data.blocked_users })} · {t('admin.overview.blockedStores', { count: data.blocked_stores })}
              </p>
            </section>
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <h2 className="mb-2 text-h3"><Link to="/admin/channels" className="hover:underline">{t('admin.overview.channels')}</Link></h2>
                {data.channels.length ? (
                  <ul className="grid gap-2">
                    {data.channels.map((ch) => (
                      <li key={ch.id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                        <span className="font-medium">@{ch.username} {!ch.enabled && <Badge>{t('admin.channels.disabled')}</Badge>}</span>
                        <ChannelState ch={ch} />
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-muted">{t('admin.overview.noChannels')}</p>}
              </Card>
              <Card>
                <h2 className="mb-1 text-h3"><Link to="/admin/log" className="hover:underline">{t('admin.overview.lastActions')}</Link></h2>
                {data.last_actions.length ? <ul>{data.last_actions.map((a) => <LogLine key={a.id} a={a} />)}</ul>
                  : <p className="text-sm text-muted">{t('admin.log.empty')}</p>}
              </Card>
            </div>
            {/* Every section, also those without a phone tab */}
            <nav aria-label={t('admin.menu')} className="md:hidden">
              <ul className="grid grid-cols-2 gap-2">
                {ADMIN_SECTIONS.slice(1).map(({ to, key, icon: Icon }) => (
                  <li key={key}>
                    <Link to={to} className="flex min-h-12 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium">
                      <Icon className="size-4 shrink-0 text-muted" aria-hidden />{t(`admin.nav.${key}`)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        )}
      </Loading>
    </>
  )
}

// --- the journal ------------------------------------------------------------------------------------------------------

export function AdminLog() {
  const { t } = useTranslation()
  const [f, setF] = useState({ action: '', date_from: '', date_to: '' })
  const [data] = useAdminData('/admin/log', f)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  return (
    <>
      <PageTitle title={t('admin.log.title')} />
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Select label={t('admin.log.type')} value={f.action} onChange={set('action')}>
          <option value="">{t('admin.all')}</option>
          {LOG_GROUPS.map((g) => <option key={g} value={g}>{t(`admin.log.groups.${g}`)}</option>)}
        </Select>
        <Input label={t('admin.log.from')} type="date" value={f.date_from} onChange={set('date_from')} />
        <Input label={t('admin.log.to')} type="date" value={f.date_to} onChange={set('date_to')} />
      </div>
      <Loading data={data} empty={t('admin.log.empty')}>
        <Card><ul>{data?.map((a) => <LogLine key={a.id} a={a} />)}</ul></Card>
      </Loading>
    </>
  )
}

// --- users ------------------------------------------------------------------------------------------------------------

export function AdminUsers() {
  const { t } = useTranslation()
  const [f, setF] = useState({ q: '', role: '', blocked: '' })
  const [data, reload] = useAdminData('/admin/users', f)
  const [action, setAction] = useState(null)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const block = (u, blocked) => setAction({
    title: blocked ? t('admin.users.block') : t('admin.users.unblock'), danger: blocked, required: blocked,
    fieldHint: blocked ? t('admin.reasonHint') : null, hint: blocked ? t('admin.reports.blockUserHint') : null,
    field: blocked ? undefined : false,
    onConfirm: async (reason) => { await api.post(`/admin/users/${u.id}/block`, { blocked, reason }); reload() },
  })
  return (
    <>
      <PageTitle title={t('admin.users.title')} hint={t('admin.users.noAdminHere')} />
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Input label={t('admin.users.search')} value={f.q} onChange={set('q')} type="search" />
        <Select label={t('admin.users.role')} value={f.role} onChange={set('role')}>
          <option value="">{t('admin.all')}</option>
          {['buyer', 'seller', 'admin'].map((r) => <option key={r} value={r}>{t(`roles.${r}`)}</option>)}
        </Select>
        <Select label={t('admin.users.blockedFilter')} value={f.blocked} onChange={set('blocked')}>
          <option value="">{t('admin.all')}</option>
          <option value="true">{t('admin.stores.blockedYes')}</option>
          <option value="false">{t('admin.stores.blockedNo')}</option>
        </Select>
      </div>
      <Loading data={data}>
        <ul className="grid gap-2">
          {data?.map((u) => (
            <li key={u.id}>
              <Card padded={false} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="font-medium break-all">{u.email}</p>
                  <p className="text-xs text-muted">
                    {t(`roles.${u.role}`)} · {t('admin.users.registered', { date: formatDate(u.created_at) })}
                    {u.store && <> · {t('admin.users.store', { name: u.store })}</>}
                  </p>
                  {u.blocked && <p className="mt-1 text-xs text-danger"><Badge tone="danger">{t('admin.users.blockedBadge')}</Badge> {u.block_reason}</p>}
                </div>
                {u.role !== 'admin' && (
                  <Button size="sm" variant={u.blocked ? 'secondary' : 'danger'} onClick={() => block(u, !u.blocked)}>
                    {u.blocked ? t('admin.users.unblock') : t('admin.users.block')}
                  </Button>
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

export { actionGroup }
