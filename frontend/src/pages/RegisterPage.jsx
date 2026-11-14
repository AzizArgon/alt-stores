import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { AuthShell, ErrorText, RoleCards, SubmitButton, brand, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput } from '../components/ui'
import { goTo } from '../config/sites'
import api, { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { registerRole, returnTo } from '../services/roles'

// Phase 16.3: one registration. First "who are you" (a buyer or a store), then email and password;
// /register?role=seller opens it with "I am a store" chosen. After it — the cabinet or the storefront by role.
export default function RegisterPage() {
  const { t } = useTranslation()
  const { register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [role, setRole] = useState(() => registerRole(location.search))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
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
    if (!role) found.role = t('auth.roleRequired')
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
      const user = await register(email, password, role, invite)
      goTo(navigate, returnTo(user, location.state?.from))
    } catch (err) {
      const key = errorKey(err)
      setErrors({ [fieldOfError(key)]: t(key) })
      setBusy(false)
    }
  }

  return (
    <AuthShell mode="register" title={t('auth.signUpTitle', brand)}>
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <RoleCards value={role} onChange={setRole} error={errors.role} />
        <Input label={t('auth.email')} type="email" autoComplete="email" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <PasswordInput label={t('auth.password')} autoComplete="new-password" error={errors.password} hint={t('errors.passwordLength')}
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <PasswordInput label={t('auth.passwordConfirm')} autoComplete="new-password" error={errors.confirm}
            value={confirm} onChange={(e) => setConfirm(e.target.value)} />
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
    </AuthShell>
  )
}
