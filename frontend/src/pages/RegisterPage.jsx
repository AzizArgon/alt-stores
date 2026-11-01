import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, SocialButtons, SubmitButton, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput } from '../components/ui'
import api, { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'

const ROLES = [
  { value: 'buyer', hint: 'auth.roleBuyerHint' },
  { value: 'seller', hint: 'auth.roleSellerHint' },
]

export default function RegisterPage() {
  const { t } = useTranslation()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [role, setRole] = useState('buyer')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [invite, setInvite] = useState('')
  // On the public demo sellers register only with an invite code
  const [inviteRequired, setInviteRequired] = useState(false)

  useEffect(() => {
    api.get('/auth/options').then((res) => setInviteRequired(res.data.seller_invite_required)).catch(() => {})
  }, [])

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = {}
    const emailError = emailErrorKey(email)
    if (emailError) found.email = t(emailError)
    // Same limits as the backend (bcrypt allows max 72 bytes)
    if (password.length < 8 || password.length > 72) found.password = t('errors.passwordLength')
    if (password !== confirm) found.confirm = t('errors.passwordMismatch')
    if (role === 'seller' && inviteRequired && !invite.trim()) found.invite = t('errors.required')
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await register(email, password, role, invite)
      navigate('/')
    } catch (err) {
      const key = errorKey(err)
      setErrors({ [fieldOfError(key)]: t(key) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t('auth.registerTitle')} hint={t('auth.registerHint')}>
      <SocialButtons />
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <Input label={t('auth.email')} type="email" autoComplete="email" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label={t('auth.password')} autoComplete="new-password" error={errors.password} hint={t('errors.passwordLength')}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <PasswordInput label={t('auth.passwordConfirm')} autoComplete="new-password" error={errors.confirm}
          value={confirm} onChange={(e) => setConfirm(e.target.value)} />

        <div>
          <span className="mb-1.5 block text-sm font-medium">{t('auth.role')}</span>
          <div className="grid grid-cols-2 gap-2">
            {ROLES.map((r) => (
              <button key={r.value} type="button" onClick={() => setRole(r.value)} aria-pressed={role === r.value}
                className={`rounded-md border px-3 py-2.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
                  role === r.value ? 'border-primary bg-primary-soft' : 'border-line-strong hover:bg-surface-2'}`}>
                <span className={`block text-sm font-semibold ${role === r.value ? 'text-primary' : ''}`}>{t(`roles.${r.value}`)}</span>
                <span className="block text-xs text-muted">{t(r.hint)}</span>
              </button>
            ))}
          </div>
        </div>

        {role === 'seller' && inviteRequired && (
          <Input label={t('auth.inviteCode')} autoComplete="off" error={errors.invite} hint={t('auth.inviteHint')}
            value={invite} onChange={(e) => setInvite(e.target.value)} />
        )}

        <div className="mt-1">
          <ErrorText>{errors.form}</ErrorText>
          <SubmitButton busy={busy} busyText={t('auth.loading')}>{t('auth.submitRegister')}</SubmitButton>
        </div>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {t('auth.haveAccount')}{' '}
        <Link to="/login" className="font-semibold text-primary hover:underline">{t('nav.login')}</Link>
      </p>
    </AuthCard>
  )
}
