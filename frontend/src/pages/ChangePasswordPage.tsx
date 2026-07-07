import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import PasswordInput from '../components/PasswordInput'

export default function ChangePasswordPage() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setToken } = useAuth()
  const nav = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) { setError('Passwords do not match'); return }
    if (next.length < 8) { setError('Password must be at least 8 characters'); return }
    setBusy(true)
    setError('')
    try {
      const resp = await changePassword(current, next)
      setToken(resp.access_token)
      nav('/dashboard', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(msg || 'Password change failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">⚡ batmonai</div>
        <h2 style={{ marginBottom: '0.25rem' }}>Set your password</h2>
        <p className="auth-sub" style={{ marginTop: 0 }}>
          You must change your password before continuing.
        </p>
        <form onSubmit={handleSubmit} className="auth-form">
          <label>Current password
            <PasswordInput value={current} onChange={setCurrent} required autoFocus />
          </label>
          <label>New password
            <PasswordInput value={next} onChange={setNext} required minLength={8} />
          </label>
          <label>Confirm new password
            <PasswordInput value={confirm} onChange={setConfirm} required />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Set password & continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
