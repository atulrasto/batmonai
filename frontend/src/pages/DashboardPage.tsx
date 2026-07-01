import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Site, Appliance, Client, AppEvent } from '../types'
import { listSites, listAppliances, listClients, listEvents } from '../api/resources'
import { useAuth } from '../context/AuthContext'

const POLL_MS = 30_000

function isOnline(app: Appliance): boolean {
  return !!app.last_seen_at && (Date.now() - new Date(app.last_seen_at).getTime()) < 60_000
}

function SummaryCard({ label, value, cls }: { label: string; value: number | string; cls?: string }) {
  return (
    <div className="summary-card">
      <div className={`summary-value ${cls ?? ''}`}>{value}</div>
      <div className="summary-label">{label}</div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const nav = useNavigate()
  const isSu = user?.role === 'superuser'

  const [sites, setSites] = useState<Site[]>([])
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [events, setEvents] = useState<AppEvent[]>([])
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const [s, a, ev] = await Promise.all([
        listSites(),
        listAppliances(),
        listEvents({ open_only: true, limit: 20 }),
      ])
      setSites(s)
      setAppliances(a)
      setEvents(ev)
      if (isSu) setClients(await listClients())
    } finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [])

  if (loading) return <div className="page-loading">Loading…</div>

  const onlineCount = appliances.filter(isOnline).length
  const criticalCount = events.filter(e => e.severity === 'critical').length
  const warningCount = events.filter(e => e.severity === 'warning').length

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
      </div>

      {/* Summary row */}
      <div className="summary-row">
        {isSu && <SummaryCard label="Clients" value={clients.length} />}
        <SummaryCard label="Sites" value={sites.length} />
        <SummaryCard label="Appliances" value={appliances.length} />
        <SummaryCard label="Online" value={onlineCount}
          cls={onlineCount === appliances.length ? 'val-ok' : onlineCount === 0 ? 'val-warn' : 'val-orange'} />
        <SummaryCard label="Open events" value={events.length}
          cls={criticalCount > 0 ? 'val-warn' : warningCount > 0 ? 'val-orange' : ''} />
      </div>

      {/* Open events panel */}
      {events.length > 0 && (
        <section className="section">
          <div className="section-header">
            <h2 className="section-title">Open Events</h2>
          </div>
          <table className="events-table">
            <thead>
              <tr><th>Time</th><th>Kind</th><th>Severity</th><th>Appliance</th></tr>
            </thead>
            <tbody>
              {events.map(ev => {
                const app = appliances.find(a => a.id === ev.appliance_id)
                return (
                  <tr key={ev.id} className="event-open"
                    style={{ cursor: app ? 'pointer' : 'default' }}
                    onClick={() => app && nav(`/appliances/${app.id}`)}>
                    <td className="muted" style={{ whiteSpace: 'nowrap' }}>
                      {new Date(ev.started_at).toLocaleString()}
                    </td>
                    <td><code>{ev.kind}</code></td>
                    <td>
                      <span className={`badge ${
                        ev.severity === 'critical' ? 'badge-red' :
                        ev.severity === 'warning' ? 'badge-orange' : 'badge-blue'
                      }`}>{ev.severity}</span>
                    </td>
                    <td className="muted">{app?.appliance_uid ?? ev.appliance_id}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      )}

      {/* Sites + appliances tree */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">Sites</h2>
          <button className="btn-ghost btn-sm" onClick={() => nav('/sites')}>
            Manage →
          </button>
        </div>
        {sites.length === 0 ? (
          <div className="empty-state-sm">No sites yet.</div>
        ) : (
          <div className="site-list">
            {sites.map(site => {
              const siteApps = appliances.filter(a => a.site_id === site.id)
              const clientName = isSu
                ? clients.find(c => c.id === site.client_id)?.name
                : undefined
              return (
                <div key={site.id} className="site-card">
                  <div className="site-card-header">
                    <div>
                      <span className="site-name">{site.name}</span>
                      {site.location && <span className="muted"> · {site.location}</span>}
                      {clientName && <span className="muted"> · {clientName}</span>}
                    </div>
                    <span className="muted" style={{ fontSize: '0.85rem' }}>
                      {siteApps.filter(isOnline).length}/{siteApps.length} online
                    </span>
                  </div>
                  {siteApps.length === 0 ? (
                    <p className="muted sub-empty">No appliances.</p>
                  ) : (
                    <div className="appliance-list">
                      {siteApps.map(app => {
                        const online = isOnline(app)
                        const appEvents = events.filter(e => e.appliance_id === app.id)
                        const hasCrit = appEvents.some(e => e.severity === 'critical')
                        const hasWarn = appEvents.some(e => e.severity === 'warning')
                        return (
                          <div key={app.id} className="appliance-row"
                            style={{ cursor: 'pointer' }}
                            onClick={() => nav(`/appliances/${app.id}`)}>
                            <div>
                              <span className="app-name">{app.name}</span>
                              <span className="muted app-uid"> · {app.appliance_uid}</span>
                            </div>
                            <div className="app-meta" style={{ gap: '0.5rem' }}>
                              {hasCrit && <span className="badge badge-red">critical</span>}
                              {!hasCrit && hasWarn && <span className="badge badge-orange">warning</span>}
                              <span className={`badge ${online ? 'badge-green' : 'badge-grey'}`}>
                                {online ? 'online' : 'offline'}
                              </span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
