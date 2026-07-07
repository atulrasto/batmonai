import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import PasswordInput from '../components/PasswordInput'

export default function AccountPage() {
  const { user, setToken } = useAuth()
  const nav = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) { setError('Passwords do not match'); return }
    if (next.length < 8) { setError('Password must be at least 8 characters'); return }
    setBusy(true)
    setError('')
    setSuccess(false)
    try {
      const resp = await changePassword(current, next)
      setToken(resp.access_token)
      setSuccess(true)
      setCurrent('')
      setNext('')
      setConfirm('')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(msg || 'Password change failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>My Account</h1>
      </div>

      {/* User info */}
      <div className="account-info-card">
        <div className="account-info-row">
          <span className="account-info-label">Email</span>
          <span className="account-info-value">{user?.email}</span>
        </div>
        <div className="account-info-row">
          <span className="account-info-label">Role</span>
          <span className={`role-badge ${user?.role === 'superuser' ? 'role-su' : 'role-client'}`}>
            {user?.role === 'superuser' ? 'admin' : 'client'}
          </span>
        </div>
      </div>

      {/* Change password */}
      <div className="account-pw-card">
        <h2 className="account-section-title">Change Password</h2>
        <form onSubmit={handleSubmit} className="auth-form" style={{ maxWidth: 380 }}>
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
          {success && (
            <p className="form-message form-message-ok">✓ Password changed successfully.</p>
          )}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Saving…' : 'Change password'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => nav(-1)}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
