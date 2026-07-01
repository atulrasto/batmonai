import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts'
import type { DcPoint } from '../types'
import { dcRange } from '../api/readings'

type Range = '1h' | '6h' | '24h' | '7d' | '30d'

const RANGE_OFFSETS: Record<Range, number> = {
  '1h': 3600_000,
  '6h': 6 * 3600_000,
  '24h': 24 * 3600_000,
  '7d': 7 * 86400_000,
  '30d': 30 * 86400_000,
}

function fmtTime(iso: string, range: Range) {
  const d = new Date(iso)
  if (range === '30d' || range === '7d') return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface Props { batteryId: string; label: string }

export default function BatteryChart({ batteryId, label }: Props) {
  const [range, setRange] = useState<Range>('6h')
  const [data, setData] = useState<DcPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError('')
    const now = Date.now()
    const from = new Date(now - RANGE_OFFSETS[range]).toISOString()
    const to = new Date(now).toISOString()
    dcRange(batteryId, from, to)
      .then(pts => { if (!cancelled) setData(pts) })
      .catch(() => { if (!cancelled) setError('Failed to load chart data') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [batteryId, range])

  const chartData = data.map(p => ({
    t: fmtTime(p.t, range),
    'Voltage (V)': +p.v_avg.toFixed(3),
    'Current (A)': +p.i_avg.toFixed(2),
  }))

  return (
    <div className="chart-card">
      <div className="chart-header">
        <span className="chart-title">{label} — History</span>
        <div className="range-tabs">
          {(['1h', '6h', '24h', '7d', '30d'] as Range[]).map(r => (
            <button key={r} className={`range-tab ${range === r ? 'active' : ''}`}
              onClick={() => setRange(r)}>{r}</button>
          ))}
        </div>
      </div>
      {loading && <div className="chart-loading">Loading…</div>}
      {error && <div className="chart-error">{error}</div>}
      {!loading && !error && data.length === 0 && (
        <div className="chart-empty">No data in this range</div>
      )}
      {!loading && !error && data.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis dataKey="t" tick={{ fill: '#8b949e', fontSize: 11 }}
              interval="preserveStartEnd" />
            <YAxis yAxisId="v" domain={['auto', 'auto']}
              tick={{ fill: '#8b949e', fontSize: 11 }} width={45} />
            <YAxis yAxisId="i" orientation="right" domain={['auto', 'auto']}
              tick={{ fill: '#8b949e', fontSize: 11 }} width={45} />
            <Tooltip
              contentStyle={{ background: '#161b22', border: '1px solid #30363d', color: '#c9d1d9' }}
              labelStyle={{ color: '#8b949e' }}
            />
            <Legend wrapperStyle={{ color: '#c9d1d9', fontSize: 12 }} />
            <Line yAxisId="v" type="monotone" dataKey="Voltage (V)"
              stroke="#58a6ff" dot={false} strokeWidth={1.5} />
            <Line yAxisId="i" type="monotone" dataKey="Current (A)"
              stroke="#3fb950" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
