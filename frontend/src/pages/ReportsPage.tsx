import { useEffect, useState } from 'react'
import type { Appliance, Battery, AcChannel, Site } from '../types'
import { listSites, listAppliances, listBatteries, listAcChannels } from '../api/resources'
import { downloadBatteryPdf, downloadAcChannelPdf, emailBatteryReport, emailAcChannelReport } from '../api/reports'

function todayLocal(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

type ReportKind = 'battery' | 'ac'

export default function ReportsPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [batteries, setBatteries] = useState<Battery[]>([])
  const [channels, setChannels] = useState<AcChannel[]>([])
  const [loading, setLoading] = useState(true)

  const [kind, setKind] = useState<ReportKind>('battery')
  const [selectedAppId, setSelectedAppId] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [reportDate, setReportDate] = useState(todayLocal())
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

  useEffect(() => {
    Promise.all([listSites(), listAppliances(), listBatteries(), listAcChannels()])
      .then(([s, a, b, c]) => { setSites(s); setAppliances(a); setBatteries(b); setChannels(c) })
      .finally(() => setLoading(false))
  }, [])

  // Derive filtered lists based on selected appliance
  const appBatteries = batteries.filter(b => !selectedAppId || b.appliance_id === selectedAppId)
  const appChannels  = channels.filter(c => !selectedAppId || c.appliance_id === selectedAppId)

  // Reset item selection when appliance or kind changes
  function handleAppChange(id: string) { setSelectedAppId(id); setSelectedId('') }
  function handleKindChange(k: ReportKind) { setKind(k); setSelectedId('') }

  async function handleDownload() {
    if (!selectedId) return
    setBusy(true); setMessage(null)
    try {
      const date = new Date(reportDate + 'T00:00:00Z')
      if (kind === 'battery') await downloadBatteryPdf(selectedId, date)
      else await downloadAcChannelPdf(selectedId, date)
      setMessage({ text: 'PDF downloaded.', ok: true })
    } catch {
      setMessage({ text: 'Failed to generate PDF.', ok: false })
    } finally { setBusy(false) }
  }

  async function handleEmail() {
    if (!selectedId) return
    setBusy(true); setMessage(null)
    try {
      const date = new Date(reportDate + 'T00:00:00Z')
      let res: { sent_to: string }
      if (kind === 'battery') res = await emailBatteryReport(selectedId, date)
      else res = await emailAcChannelReport(selectedId, date)
      setMessage({ text: `Report sent to ${res.sent_to}.`, ok: true })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setMessage({ text: detail || 'Failed to send email.', ok: false })
    } finally { setBusy(false) }
  }

  if (loading) return <div className="page-loading">Loading…</div>

  // Build appliance label with site name
  const appLabel = (app: Appliance) => {
    const site = sites.find(s => s.id === app.site_id)
    return `${site?.name ?? '—'} / ${app.name} (${app.appliance_uid})`
  }

  const selectedItem = kind === 'battery'
    ? batteries.find(b => b.id === selectedId)
    : channels.find(c => c.id === selectedId)

  const canAct = !!selectedId && !!reportDate

  return (
    <div className="page">
      <div className="page-header">
        <h1>Reports</h1>
      </div>

      <div className="report-form">
        {/* Report type */}
        <div className="form-group">
          <label className="form-label">Report type</label>
          <div className="radio-group">
            <label className="radio-label">
              <input type="radio" checked={kind === 'battery'} onChange={() => handleKindChange('battery')} />
              Battery (DC)
            </label>
            <label className="radio-label">
              <input type="radio" checked={kind === 'ac'} onChange={() => handleKindChange('ac')} />
              AC Channel / Inverter
            </label>
          </div>
        </div>

        {/* Appliance filter */}
        <div className="form-group">
          <label className="form-label">Appliance (optional filter)</label>
          <select value={selectedAppId} onChange={e => handleAppChange(e.target.value)} className="form-select">
            <option value="">All appliances</option>
            {appliances.map(a => (
              <option key={a.id} value={a.id}>{appLabel(a)}</option>
            ))}
          </select>
        </div>

        {/* Battery or AC channel selector */}
        <div className="form-group">
          <label className="form-label">
            {kind === 'battery' ? 'Battery' : 'AC Channel'}
          </label>
          <select value={selectedId} onChange={e => setSelectedId(e.target.value)} className="form-select">
            <option value="">Select…</option>
            {kind === 'battery'
              ? appBatteries.map(b => (
                  <option key={b.id} value={b.id}>
                    {b.name || b.battery_uid} · addr {b.modbus_addr}
                  </option>
                ))
              : appChannels.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.role}
                  </option>
                ))
            }
          </select>
        </div>

        {/* Date picker */}
        <div className="form-group">
          <label className="form-label">Report date</label>
          <input
            type="date"
            value={reportDate}
            max={todayLocal()}
            onChange={e => setReportDate(e.target.value)}
            className="form-input"
            style={{ width: 180 }}
          />
        </div>

        {/* Selected item info */}
        {selectedItem && (
          <div className="report-preview">
            <span className="muted">
              {kind === 'battery'
                ? `${(selectedItem as Battery).battery_uid} · ${(selectedItem as Battery).nominal_v} V nominal · ${(selectedItem as Battery).shunt_rating_a} A shunt`
                : `${(selectedItem as AcChannel).channel_uid} · ${(selectedItem as AcChannel).role}`
              }
            </span>
          </div>
        )}

        {/* Actions */}
        <div className="form-actions">
          <button
            className="btn-primary"
            onClick={handleDownload}
            disabled={!canAct || busy}
          >
            {busy ? 'Generating…' : '⬇ Download PDF'}
          </button>
          <button
            className="btn-ghost"
            onClick={handleEmail}
            disabled={!canAct || busy}
            title="Sends to the client's registered email"
          >
            {busy ? '…' : '✉ Email PDF'}
          </button>
        </div>

        {message && (
          <div className={`form-message ${message.ok ? 'form-message-ok' : 'form-message-err'}`}>
            {message.text}
          </div>
        )}
      </div>
    </div>
  )
}
