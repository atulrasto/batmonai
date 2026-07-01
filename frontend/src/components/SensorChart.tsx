import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'
import type { SensorPoint } from '../types'
import { sensorRange } from '../api/readings'

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

interface Props { sensorId: string; sensorType: string; label: string }

export default function SensorChart({ sensorId, sensorType, label }: Props) {
  const [range, setRange] = useState<Range>('6h')
  const [data, setData] = useState<SensorPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError('')
    const now = Date.now()
    const from = new Date(now - RANGE_OFFSETS[range]).toISOString()
    const to = new Date(now).toISOString()
    sensorRange(sensorId, from, to)
      .then(pts => { if (!cancelled) setData(pts) })
      .catch(() => { if (!cancelled) setError('Failed to load chart data') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sensorId, range])

  const isTH = sensorType === 'temp_humidity'
  const isH2 = sensorType === 'gas_h2'

  const chartData = data.map(p => {
    const base = { t: fmtTime(p.t, range) }
    if (isTH) return {
      ...base,
      'Temp (°C)': +(Number(p.payload.temperature_c) || 0).toFixed(1),
      'Humidity (%)': +(Number(p.payload.humidity_pct) || 0).toFixed(1),
    }
    if (isH2) return {
      ...base,
      'H₂ (ppm)': +(Number(p.payload.ppm) || 0).toFixed(1),
    }
    return base
  })

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
      {!loading && !error && data.length > 0 && isTH && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis dataKey="t" tick={{ fill: '#8b949e', fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis yAxisId="temp" domain={['auto', 'auto']}
              tick={{ fill: '#8b949e', fontSize: 11 }} width={40} label={{ value: '°C', fill: '#8b949e', fontSize: 11, position: 'insideTopLeft' }} />
            <YAxis yAxisId="hum" orientation="right" domain={[0, 100]}
              tick={{ fill: '#8b949e', fontSize: 11 }} width={40} label={{ value: '%', fill: '#8b949e', fontSize: 11, position: 'insideTopRight' }} />
            <Tooltip
              contentStyle={{ background: '#161b22', border: '1px solid #30363d', color: '#c9d1d9' }}
              labelStyle={{ color: '#8b949e' }}
            />
            <Legend wrapperStyle={{ color: '#c9d1d9', fontSize: 12 }} />
            <Line yAxisId="temp" type="monotone" dataKey="Temp (°C)"
              stroke="#f78166" dot={false} strokeWidth={1.5} />
            <Line yAxisId="hum" type="monotone" dataKey="Humidity (%)"
              stroke="#58a6ff" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      )}
      {!loading && !error && data.length > 0 && isH2 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis dataKey="t" tick={{ fill: '#8b949e', fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis domain={[0, 'auto']} tick={{ fill: '#8b949e', fontSize: 11 }} width={45} />
            <Tooltip
              contentStyle={{ background: '#161b22', border: '1px solid #30363d', color: '#c9d1d9' }}
              labelStyle={{ color: '#8b949e' }}
            />
            <Legend wrapperStyle={{ color: '#c9d1d9', fontSize: 12 }} />
            <ReferenceLine y={50} stroke="#f85149" strokeDasharray="4 2"
              label={{ value: 'Alarm threshold', fill: '#f85149', fontSize: 11 }} />
            <Line type="monotone" dataKey="H₂ (ppm)"
              stroke="#d2a8ff" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
