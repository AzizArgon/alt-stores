import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { AuthShell, ErrorText, SubmitButton, brand, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput } from '../components/ui'
import { goTo } from '../config/sites'
import { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { returnTo } from '../services/roles'

// Phase 16.3: one login for buyers, stores and the admin. The role is not chosen: the account knows it, and
// returnTo() sends each role to its own section (or back to the page the guest came from).
// The server keeps the admin's strict attempt limit and login journal on this same door.
export default function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
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
      const user = await login(email, password)
      goTo(navigate, returnTo(user, location.state?.from))
    } catch (err) {
      const key = errorKey(err)
      const detail = err.response?.data?.detail  // a blocked user: {code: 'user_blocked', reason}; the limit: {minutes}
      setErrors({ [fieldOfError(key)]: t(key, typeof detail === 'object' ? detail : {}) })
      setBusy(false)
    }
  }

  return (
    <AuthShell mode="login" title={t('auth.signInTitle', brand)}>
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
    </AuthShell>
  )
}
