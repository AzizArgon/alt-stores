import { TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LogoMark } from './Logo'
import { Badge, Button, Card } from './ui'

// Shared building blocks for the login and register pages
export function AuthCard({ title, hint, children }) {
  return (
    <Card className="mx-auto max-w-md md:mt-4 md:!p-8">
      <LogoMark className="size-10" />
      <h1 className="mt-4 text-h1">{title}</h1>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
      <div className="mt-6">{children}</div>
    </Card>
  )
}

const GOOGLE_PATHS = [
  ['#4285F4', 'M22.5 12.2c0-.8-.1-1.5-.2-2.2H12v4.2h5.9a5 5 0 0 1-2.2 3.3v2.7h3.5c2.1-1.9 3.3-4.7 3.3-8z'],
  ['#34A853', 'M12 23c3 0 5.5-1 7.2-2.8l-3.5-2.7c-1 .7-2.2 1-3.7 1-2.9 0-5.3-1.9-6.2-4.5H2.2v2.8A11 11 0 0 0 12 23z'],
  ['#FBBC05', 'M5.8 14c-.2-.7-.4-1.3-.4-2s.2-1.3.4-2V7.2H2.2a11 11 0 0 0 0 9.6z'],
  ['#EA4335', 'M12 5.4c1.6 0 3 .6 4.1 1.6l3.1-3.1A11 11 0 0 0 2.2 7.2L5.8 10c.9-2.6 3.3-4.6 6.2-4.6z'],
]

// Places for the sign-in services, connected in phase B3
export function SocialButtons() {
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
      <div className="my-5 flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />{t('auth.or')}<span className="h-px flex-1 bg-line" />
      </div>
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
