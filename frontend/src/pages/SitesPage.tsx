import { useEffect, useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Site, Appliance, Client } from '../types'
import { listSites, createSite, listAppliances, createAppliance, listClients } from '../api/resources'
import { useAuth } from '../context/AuthContext'

export default function SitesPage() {
  const { user } = useAuth()
  const isSu = user?.role === 'superuser'
  const nav = useNavigate()

  const [sites, setSites] = useState<Site[]>([])
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)

  const [showSiteForm, setShowSiteForm] = useState(false)
  const [siteName, setSiteName] = useState('')
  const [siteClientId, setSiteClientId] = useState('')
  const [siteLocation, setSiteLocation] = useState('')
  const [siteBusy, setSiteBusy] = useState(false)
  const [siteError, setSiteError] = useState('')

  const [showAppForm, setShowAppForm] = useState<string | null>(null) // siteId
  const [appName, setAppName] = useState('')
  const [appSecret, setAppSecret] = useState('')
  const [appBusy, setAppBusy] = useState(false)
  const [appError, setAppError] = useState('')

  async function load() {
    try {
      const [s, a] = await Promise.all([listSites(), listAppliances()])
      setSites(s)
      setAppliances(a)
      if (isSu) setClients(await listClients())
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleCreateSite(e: FormEvent) {
    e.preventDefault()
    setSiteBusy(true); setSiteError('')
    try {
      await createSite(siteName, isSu ? siteClientId : undefined, siteLocation || undefined)
      setSiteName(''); setSiteClientId(''); setSiteLocation('')
      setShowSiteForm(false)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSiteError(msg || 'Failed to create site')
    } finally { setSiteBusy(false) }
  }

  async function handleCreateAppliance(e: FormEvent, siteId: string) {
    e.preventDefault()
    setAppBusy(true); setAppError('')
    try {
      const clientId = isSu ? sites.find(s => s.id === siteId)?.client_id : undefined
      await createAppliance({ site_id: siteId, name: appName, device_secret: appSecret, client_id: clientId })
      setAppName(''); setAppSecret(''); setShowAppForm(null)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAppError(msg || 'Failed to create appliance')
    } finally { setAppBusy(false) }
  }

  if (loading) return <div className="page-loading">Loading…</div>

  return (
    <div className="page">
      <div className="page-header">
        <h1>Sites</h1>
        <button className="btn-primary" onClick={() => setShowSiteForm(s => !s)}>
          {showSiteForm ? 'Cancel' : '+ New site'}
        </button>
      </div>

      {showSiteForm && (
        <form className="inline-form" onSubmit={handleCreateSite}>
          {isSu && (
            <select required value={siteClientId} onChange={e => setSiteClientId(e.target.value)}>
              <option value="">Select client…</option>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <input placeholder="Site name" required value={siteName}
            onChange={e => setSiteName(e.target.value)} />
          <input placeholder="Location (optional)" value={siteLocation}
            onChange={e => setSiteLocation(e.target.value)} />
          {siteError && <span className="form-error">{siteError}</span>}
          <button type="submit" className="btn-primary" disabled={siteBusy}>
            {siteBusy ? 'Creating…' : 'Create site'}
          </button>
        </form>
      )}

      {sites.length === 0 ? (
        <div className="empty-state">No sites yet.</div>
      ) : (
        <div className="site-list">
          {sites.map(site => {
            const siteApps = appliances.filter(a => a.site_id === site.id)
            return (
              <div key={site.id} className="site-card">
                <div className="site-card-header">
                  <div>
                    <span className="site-name">{site.name}</span>
                    {site.location && <span className="muted"> · {site.location}</span>}
                  </div>
                  <button className="btn-ghost btn-sm"
                    onClick={() => { setShowAppForm(showAppForm === site.id ? null : site.id); setAppError('') }}>
                    {showAppForm === site.id ? 'Cancel' : '+ Appliance'}
                  </button>
                </div>

                {showAppForm === site.id && (
                  <form className="inline-form sub-form" onSubmit={e => handleCreateAppliance(e, site.id)}>
                    <input placeholder="Appliance name" required value={appName}
                      onChange={e => setAppName(e.target.value)} />
                    <input placeholder="Device secret (MQTT password)" required value={appSecret}
                      onChange={e => setAppSecret(e.target.value)} />
                    {appError && <span className="form-error">{appError}</span>}
                    <button type="submit" className="btn-primary btn-sm" disabled={appBusy}>
                      {appBusy ? 'Creating…' : 'Add appliance'}
                    </button>
                  </form>
                )}

                {siteApps.length === 0 ? (
                  <p className="muted sub-empty">No appliances yet.</p>
                ) : (
                  <div className="appliance-list">
                    {siteApps.map(app => (
                      <div key={app.id} className="appliance-row"
                        onClick={() => nav(`/appliances/${app.id}`)}>
                        <div>
                          <span className="app-name">{app.name}</span>
                          <span className="muted app-uid"> · {app.appliance_uid}</span>
                        </div>
                        <div className="app-meta">
                          <span className={`badge ${app.is_active ? 'badge-green' : 'badge-grey'}`}>
                            {app.is_active ? 'active' : 'inactive'}
                          </span>
                          {app.last_seen_at && (
                            <span className="muted">
                              seen {new Date(app.last_seen_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
