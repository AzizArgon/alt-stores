import { ShieldCheck, Store, Tags, TriangleAlert, UserRound, CalendarCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { BRAND } from '../config/brand'
import { LogoMark } from './Logo'
import { Badge, Button, Card } from './ui'

// Phase 16.3: one window for the login and the registration of every role.
// Phone: one column (tabs, title, sign-in services, form). From lg (PC, wide tablet): a horizontal card —
// on the left the brand, 3 advantages and the sign-in services, on the right the form.
const PERKS = [[Tags, 'auth.perkCompare'], [ShieldCheck, 'auth.perkHonest'], [CalendarCheck, 'auth.perkReserve']]

export function AuthShell({ mode, title, children }) {
  const { t } = useTranslation()
  return (
    <Card padded={false} className="mx-auto w-full max-w-md overflow-hidden lg:grid lg:max-w-5xl lg:grid-cols-[5fr_6fr]">
      <aside className="hidden flex-col bg-primary-soft p-10 lg:flex">
        <LogoMark className="size-11" />
        <p className="mt-5 text-h2 leading-snug">{t('auth.panelTitle')}</p>
        <ul className="mt-6 grid gap-4">
          {PERKS.map(([Icon, key]) => (
            <li key={key} className="flex items-center gap-3 text-sm">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface text-primary"><Icon className="size-5" aria-hidden /></span>
              {t(key)}
            </li>
          ))}
        </ul>
        <div className="mt-auto pt-8"><SocialButtons divider={false} /></div>
      </aside>
      <div className="p-5 sm:p-8 lg:p-10">
        <AuthTabs mode={mode} />
        <h1 className="mt-5 text-h1">{title}</h1>
        <div className="mt-5 lg:hidden"><SocialButtons /></div>
        <div className="lg:mt-5">{children}</div>
      </div>
    </Card>
  )
}

// "Вход / Регистрация" in the same window; the page to return to is kept
function AuthTabs({ mode }) {
  const { t } = useTranslation()
  const { state } = useLocation()
  const tab = (key, to, label) => (
    <Link to={to} state={state} replace aria-current={mode === key ? 'page' : undefined}
      className={`flex min-h-10 flex-1 items-center justify-center rounded-md px-3 text-sm font-semibold transition-colors ${mode === key ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink'}`}>
      {label}
    </Link>
  )
  return (
    <nav className="flex gap-1 rounded-lg bg-surface-2 p-1">
      {tab('login', '/login', t('auth.tabLogin'))}
      {tab('register', '/register', t('auth.tabRegister'))}
    </nav>
  )
}

// Registration: who the account is for — two big cards, the chosen one has a blue frame
const ROLES = [['buyer', UserRound, 'auth.roleBuyer', 'auth.roleBuyerHint'], ['seller', Store, 'auth.roleSeller', 'auth.roleSellerHint']]

export function RoleCards({ value, onChange, error }) {
  const { t } = useTranslation()
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-ink">{t('auth.roleLabel')}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {ROLES.map(([role, Icon, title, hint]) => (
          <label key={role} className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 p-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${value === role ? 'border-primary bg-primary-soft' : 'border-line hover:border-line-strong'}`}>
            <input type="radio" name="role" value={role} checked={value === role} onChange={() => onChange(role)} className="sr-only" />
            <span className={`flex size-10 shrink-0 items-center justify-center rounded-md ${value === role ? 'bg-primary text-white' : 'bg-surface-2 text-muted'}`}>
              <Icon className="size-5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block font-semibold">{t(title)}</span>
              <span className="block text-xs text-muted">{t(hint)}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <p className="mt-1.5 text-sm text-danger">{error}</p>}
    </fieldset>
  )
}

export const brand = { brand: BRAND.name }

const GOOGLE_PATHS = [
  ['#4285F4', 'M22.5 12.2c0-.8-.1-1.5-.2-2.2H12v4.2h5.9a5 5 0 0 1-2.2 3.3v2.7h3.5c2.1-1.9 3.3-4.7 3.3-8z'],
  ['#34A853', 'M12 23c3 0 5.5-1 7.2-2.8l-3.5-2.7c-1 .7-2.2 1-3.7 1-2.9 0-5.3-1.9-6.2-4.5H2.2v2.8A11 11 0 0 0 12 23z'],
  ['#FBBC05', 'M5.8 14c-.2-.7-.4-1.3-.4-2s.2-1.3.4-2V7.2H2.2a11 11 0 0 0 0 9.6z'],
  ['#EA4335', 'M12 5.4c1.6 0 3 .6 4.1 1.6l3.1-3.1A11 11 0 0 0 2.2 7.2L5.8 10c.9-2.6 3.3-4.6 6.2-4.6z'],
]

// Places for the sign-in services, connected in phase B3
export function SocialButtons({ divider = true }) {
  const { t } = useTranslation()
  return (
    <>
      <div className="grid gap-2">
        <Button variant="secondary" disabled className="relative w-full !opacity-70">
          <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
            {GOOGLE_PATHS.map(([fill, d]) => <path key={fill} fill={fill} d={d} />)}
          </svg>
          {t('auth.google')}<Badge className="ml-1">{t('auth.soon')}</Badge>
        </Button>
        <Button variant="secondary" disabled className="relative w-full !opacity-70">
          <span className="rounded-sm bg-primary px-1 text-xs font-bold text-white" aria-hidden>ID</span>
          {t('auth.oneid')}<Badge className="ml-1">{t('auth.soon')}</Badge>
        </Button>
      </div>
      {divider && (
        <div className="my-5 flex items-center gap-3 text-xs text-muted">
          <span className="h-px flex-1 bg-line" />{t('auth.or')}<span className="h-px flex-1 bg-line" />
        </div>
      )}
    </>
  )
}

export function ErrorText({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="mb-4 flex gap-2 rounded-md border border-danger-line bg-danger-soft px-3 py-2 text-sm text-danger">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />{children}
    </p>
  )
}

export function SubmitButton({ busy, busyText, children }) {
  return <Button type="submit" size="lg" disabled={busy} className="w-full">{busy ? busyText : children}</Button>
}

// The message of a server error, and the field it belongs to (without a field it goes above the button)
const ERROR_FIELD = {
  'errors.emailTaken': 'email',
  'errors.invalidCredentials': 'password',
  'errors.invite_required': 'invite',
}
export const fieldOfError = (key) => ERROR_FIELD[key] || 'form'

// Same check as the browser's, with our own text
export const emailErrorKey = (email) => {
  if (!email.trim()) return 'errors.required'
  return /^\S+@\S+\.\S+$/.test(email.trim()) ? '' : 'errors.emailFormat'
}
