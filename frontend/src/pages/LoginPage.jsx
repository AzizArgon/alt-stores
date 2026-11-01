import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, SocialButtons, SubmitButton, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput } from '../components/ui'
import { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'

export default function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
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
      await login(email, password)
      navigate('/')
    } catch (err) {
      const key = errorKey(err)
      setErrors({ [fieldOfError(key)]: t(key) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t('auth.loginTitle')} hint={t('auth.loginHint')}>
      <SocialButtons />
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <Input label={t('auth.email')} type="email" autoComplete="email" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label={t('auth.password')} autoComplete="current-password" error={errors.password}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="mt-1">
          <ErrorText>{errors.form}</ErrorText>
          <SubmitButton busy={busy} busyText={t('auth.loading')}>{t('auth.submitLogin')}</SubmitButton>
        </div>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-semibold text-primary hover:underline">{t('nav.register')}</Link>
      </p>
    </AuthCard>
  )
}
