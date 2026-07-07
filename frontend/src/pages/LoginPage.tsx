import { useState, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import PasswordInput from '../components/PasswordInput'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setToken, user, loading } = useAuth()
  const nav = useNavigate()

  useEffect(() => {
    if (!loading && user && !user.must_change_password) nav('/dashboard', { replace: true })
    if (!loading && user?.must_change_password) nav('/change-password', { replace: true })
  }, [user, loading, nav])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const resp = await login(email, password)
      setToken(resp.access_token)
      if (resp.must_change_password) {
        nav('/change-password', { replace: true })
      } else {
        nav('/dashboard', { replace: true })
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(msg || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">⚡ batmonai</div>
        <p className="auth-sub">Battery & Inverter Monitoring</p>
        <form onSubmit={handleSubmit} className="auth-form">
          <label>Email
            <input
              type="email" value={email} autoFocus required
              onChange={e => setEmail(e.target.value)}
            />
          </label>
          <label>Password
            <PasswordInput value={password} onChange={setPassword} required />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
