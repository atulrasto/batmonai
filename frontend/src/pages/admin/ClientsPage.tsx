import { useEffect, useState, FormEvent } from 'react'
import type { Client } from '../../types'
import { listClients, createClient, updateClient } from '../../api/resources'
import InlineEdit from '../../components/InlineEdit'

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    try { setClients(await listClients()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await createClient(name, email)
      setName(''); setEmail(''); setShowForm(false)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Failed to create client')
    } finally { setBusy(false) }
  }

  if (loading) return <div className="page-loading">Loading…</div>

  return (
    <div className="page">
      <div className="page-header">
        <h1>Clients</h1>
        <button className="btn-primary" onClick={() => setShowForm(s => !s)}>
          {showForm ? 'Cancel' : '+ New client'}
        </button>
      </div>

      {showForm && (
        <form className="inline-form" onSubmit={handleCreate}>
          <input placeholder="Company name" required value={name}
            onChange={e => setName(e.target.value)} />
          <input placeholder="Admin email" type="email" required value={email}
            onChange={e => setEmail(e.target.value)} />
          {error && <span className="form-error">{error}</span>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Creating…' : 'Create'}
          </button>
        </form>
      )}

      {clients.length === 0 ? (
        <div className="empty-state">No clients yet. Create your first client above.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Webhook URL</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody>
            {clients.map(c => (
              <tr key={c.id}>
                <td>
                  <InlineEdit
                    value={c.name}
                    onSave={async (val) => {
                      await updateClient(c.id, { name: val })
                      setClients(prev => prev.map(x => x.id === c.id ? { ...x, name: val } : x))
                    }}
                  />
                </td>
                <td>{c.primary_email}</td>
                <td>
                  <InlineEdit
                    value={c.webhook_url ?? ''}
                    placeholder="https://…"
                    allowEmpty
                    onSave={async (val) => {
                      await updateClient(c.id, { webhook_url: val || null })
                      setClients(prev => prev.map(x => x.id === c.id ? { ...x, webhook_url: val || null } : x))
                    }}
                    inputStyle={{ width: 260, fontSize: '0.85rem' }}
                  />
                </td>
                <td>
                  <span className={`badge ${c.is_active ? 'badge-green' : 'badge-grey'}`}>
                    {c.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="muted">{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
