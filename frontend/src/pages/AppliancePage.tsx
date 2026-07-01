import { useEffect, useState, useCallback, FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { Appliance, Battery, AcChannel, Rs485Sensor, DcPoint, AcPoint, SensorPoint, AppEvent } from '../types'
import { getAppliance, listBatteries, listAcChannels, listSensors, createBattery, createAcChannel, createSensor, updateAppliance, updateBattery, updateAcChannel, updateSensor, listEvents } from '../api/resources'
import { dcLatest, acLatest, sensorLatest } from '../api/readings'
import { startSim, stopSim, simStatus } from '../api/simulator'
import BatteryChart from '../components/BatteryChart'
import AcChannelChart from '../components/AcChannelChart'
import SensorChart from '../components/SensorChart'
import InlineEdit from '../components/InlineEdit'
import { useAuth } from '../context/AuthContext'

const POLL_MS = 15_000

function voltageClass(v: number, nominal: number): string {
  if (v <= 0) return 'val-offline'
  if (v < nominal * 0.9) return 'val-warn'
  if (v > nominal * 1.2) return 'val-high'
  return 'val-ok'
}

function currentLabel(i: number): { label: string; cls: string } {
  if (i > 0.5) return { label: 'Charging', cls: 'badge-green' }
  if (i < -0.5) return { label: 'Discharging', cls: 'badge-orange' }
  return { label: 'Float', cls: 'badge-blue' }
}

export default function AppliancePage() {
  const { applianceId } = useParams<{ applianceId: string }>()
  const nav = useNavigate()
  const { user } = useAuth()

  const [appliance, setAppliance] = useState<Appliance | null>(null)
  const [batteries, setBatteries] = useState<Battery[]>([])
  const [channels, setChannels] = useState<AcChannel[]>([])
  const [dcReadings, setDcReadings] = useState<Record<string, DcPoint>>({})
  const [acReadings, setAcReadings] = useState<Record<string, AcPoint>>({})
  const [loading, setLoading] = useState(true)
  const [selectedBattery, setSelectedBattery] = useState<Battery | null>(null)
  const [selectedChannel, setSelectedChannel] = useState<AcChannel | null>(null)
  const [selectedSensor, setSelectedSensor] = useState<Rs485Sensor | null>(null)

  // Add battery form
  const [showBatForm, setShowBatForm] = useState(false)
  const [batName, setBatName] = useState('')
  const [batAddr, setBatAddr] = useState('1')
  const [batShunt, setBatShunt] = useState('100')
  const [batNominal, setBatNominal] = useState('12.0')
  const [batBusy, setBatBusy] = useState(false)
  const [batError, setBatError] = useState('')

  // Add AC channel form
  const [showAcForm, setShowAcForm] = useState(false)
  const [acName, setAcName] = useState('')
  const [acAddr, setAcAddr] = useState('10')
  const [acRole, setAcRole] = useState('inverter_input')
  const [acBusy, setAcBusy] = useState(false)
  const [acError, setAcError] = useState('')

  // Sensors
  const [sensors, setSensors] = useState<Rs485Sensor[]>([])
  const [sensorReadings, setSensorReadings] = useState<Record<string, SensorPoint>>({})
  const [showSensorForm, setShowSensorForm] = useState(false)
  const [sensorName, setSensorName] = useState('')
  const [sensorAddr, setSensorAddr] = useState('5')
  const [sensorType, setSensorType] = useState('temp_humidity')
  const [sensorBusy, setSensorBusy] = useState(false)
  const [sensorError, setSensorError] = useState('')

  // Events
  const [events, setEvents] = useState<AppEvent[]>([])
  const [eventsOpenOnly, setEventsOpenOnly] = useState(false)

  // Simulator
  const [simRunning, setSimRunning] = useState(false)

  async function loadStatic() {
    if (!applianceId) return
    const [app, allBats, allChs, allSensors] = await Promise.all([
      getAppliance(applianceId),
      listBatteries(),
      listAcChannels(),
      listSensors(),
    ])
    setAppliance(app)
    const bats = allBats.filter(b => b.appliance_id === applianceId)
    const chs = allChs.filter(c => c.appliance_id === applianceId)
    const sns = allSensors.filter(s => s.appliance_id === applianceId)
    setBatteries(bats)
    setChannels(chs)
    setSensors(sns)
    if (bats.length > 0) setSelectedBattery(bats[0])
    setLoading(false)
    return { bats, chs, sns }
  }

  const pollReadings = useCallback(async (
    bats: Battery[], chs: AcChannel[], sns: Rs485Sensor[]
  ) => {
    const dcResults = await Promise.allSettled(bats.map(b => dcLatest(b.id)))
    const newDc: Record<string, DcPoint> = {}
    dcResults.forEach((r, i) => {
      if (r.status === 'fulfilled') newDc[bats[i].id] = r.value
    })
    setDcReadings(newDc)

    const acResults = await Promise.allSettled(chs.map(c => acLatest(c.id)))
    const newAc: Record<string, AcPoint> = {}
    acResults.forEach((r, i) => {
      if (r.status === 'fulfilled') newAc[chs[i].id] = r.value
    })
    setAcReadings(newAc)

    const snResults = await Promise.allSettled(sns.map(s => sensorLatest(s.id)))
    const newSn: Record<string, SensorPoint> = {}
    snResults.forEach((r, i) => {
      if (r.status === 'fulfilled') newSn[sns[i].id] = r.value
    })
    setSensorReadings(newSn)
  }, [])

  useEffect(() => {
    let bats: Battery[] = [], chs: AcChannel[] = [], sns: Rs485Sensor[] = []
    let timer: ReturnType<typeof setInterval>

    loadStatic().then(result => {
      if (!result) return
      bats = result.bats; chs = result.chs; sns = result.sns
      pollReadings(bats, chs, sns)
      timer = setInterval(() => pollReadings(bats, chs, sns), POLL_MS)
    })

    // Check if simulator is already running for this appliance
    if (applianceId) {
      simStatus().then(s => setSimRunning(s.active.includes(applianceId))).catch(() => {})
      listEvents({ appliance_id: applianceId, limit: 50 }).then(setEvents).catch(() => {})
    }

    return () => clearInterval(timer)
  }, [applianceId])

  async function toggleSim() {
    if (!applianceId) return
    if (simRunning) {
      await stopSim(applianceId)
      setSimRunning(false)
    } else {
      await startSim(applianceId, 5)
      setSimRunning(true)
    }
  }

  async function handleAddBattery(e: FormEvent) {
    e.preventDefault()
    if (!appliance) return
    setBatBusy(true); setBatError('')
    try {
      const clientId = user?.role === 'superuser' ? appliance.client_id : undefined
      await createBattery({
        appliance_id: appliance.id,
        name: batName,
        modbus_addr: parseInt(batAddr),
        shunt_rating_a: parseInt(batShunt),
        nominal_v: parseFloat(batNominal),
        client_id: clientId,
      })
      setBatName(''); setBatAddr('1'); setBatShunt('100'); setBatNominal('12.0')
      setShowBatForm(false)
      loadStatic()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setBatError(typeof msg === 'string' ? msg : JSON.stringify(msg) || 'Failed')
    } finally { setBatBusy(false) }
  }

  async function handleAddAcChannel(e: FormEvent) {
    e.preventDefault()
    if (!appliance) return
    setAcBusy(true); setAcError('')
    try {
      const clientId = user?.role === 'superuser' ? appliance.client_id : undefined
      await createAcChannel({
        appliance_id: appliance.id,
        name: acName,
        modbus_addr: parseInt(acAddr),
        role: acRole,
        client_id: clientId,
      })
      setAcName(''); setAcAddr('10'); setAcRole('inverter_input')
      setShowAcForm(false)
      loadStatic()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setAcError(typeof msg === 'string' ? msg : JSON.stringify(msg) || 'Failed')
    } finally { setAcBusy(false) }
  }

  async function handleAddSensor(e: FormEvent) {
    e.preventDefault()
    if (!appliance) return
    setSensorBusy(true); setSensorError('')
    try {
      const clientId = user?.role === 'superuser' ? appliance.client_id : undefined
      await createSensor({
        appliance_id: appliance.id,
        sensor_type: sensorType,
        modbus_addr: parseInt(sensorAddr),
        name: sensorName,
        client_id: clientId,
      })
      setSensorName(''); setSensorAddr('5'); setSensorType('temp_humidity')
      setShowSensorForm(false)
      loadStatic()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setSensorError(typeof msg === 'string' ? msg : JSON.stringify(msg) || 'Failed')
    } finally { setSensorBusy(false) }
  }

  if (loading) return <div className="page-loading">Loading…</div>
  if (!appliance) return <div className="page-loading">Appliance not found</div>

  const lastSeen = appliance.last_seen_at
    ? new Date(appliance.last_seen_at).toLocaleString()
    : 'never'
  const isOnline = appliance.last_seen_at
    && (Date.now() - new Date(appliance.last_seen_at).getTime()) < 60_000

  return (
    <div className="page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <button className="btn-ghost btn-sm back-btn" onClick={() => nav('/sites')}>
            ← Sites
          </button>
          <h1 style={{ marginTop: '0.5rem' }}>
            <InlineEdit
              value={appliance.name}
              onSave={async (name) => {
                const updated = await updateAppliance(appliance.id, { name })
                setAppliance(updated)
              }}
              inputStyle={{ fontSize: '1.4rem', fontWeight: 700, width: 280 }}
            />
          </h1>
          <div className="muted" style={{ marginTop: '0.25rem' }}>
            {appliance.appliance_uid}
            {appliance.fw_version && <> · fw {appliance.fw_version}</>}
            {' · last seen '}{lastSeen}
            {' '}
            <span className={`badge ${isOnline ? 'badge-green' : 'badge-grey'}`}>
              {isOnline ? 'online' : 'offline'}
            </span>
          </div>
        </div>
        <button
          className={simRunning ? 'btn-sim-on' : 'btn-sim-off'}
          onClick={toggleSim}
          style={{ marginTop: '2rem', flexShrink: 0 }}
          title={simRunning ? 'Stop simulated telemetry' : 'Start simulated telemetry (5s interval)'}
        >
          {simRunning ? '⏹ Sim ON' : '▶ Simulate'}
        </button>
      </div>

      {/* AC Channels */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">AC / Inverter</h2>
          <button className="btn-ghost btn-sm" onClick={() => { setShowAcForm(s => !s); setAcError('') }}>
            {showAcForm ? 'Cancel' : '+ Add AC channel'}
          </button>
        </div>
        {showAcForm && (
          <form className="inline-form" onSubmit={handleAddAcChannel}>
            <input placeholder="Name (e.g. Mains Input)" required value={acName}
              onChange={e => setAcName(e.target.value)} />
            <input placeholder="Modbus addr" type="number" min="1" max="247" required
              value={acAddr} onChange={e => setAcAddr(e.target.value)} style={{ width: 120 }} />
            <select value={acRole} onChange={e => setAcRole(e.target.value)}>
              <option value="inverter_input">inverter_input</option>
              <option value="inverter_output">inverter_output</option>
              <option value="load">load</option>
            </select>
            {acError && <span className="form-error">{acError}</span>}
            <button type="submit" className="btn-primary btn-sm" disabled={acBusy}>
              {acBusy ? 'Adding…' : 'Add'}
            </button>
          </form>
        )}
        {channels.length > 0 ? (
          <div className="card-grid">
            {channels.map(ch => {
              const r = acReadings[ch.id]
              const mainsOk = r && r.v_avg > 50
              return (
                <div key={ch.id}
                  className={`reading-card clickable ${selectedChannel?.id === ch.id ? 'card-selected' : ''} ${mainsOk ? 'border-green' : 'border-grey'}`}
                  onClick={() => { setSelectedChannel(ch); setSelectedBattery(null); setSelectedSensor(null) }}>
                  <div className="card-title">
                    <InlineEdit
                      value={ch.name}
                      onSave={async (name) => {
                        await updateAcChannel(ch.id, { name })
                        setChannels(prev => prev.map(c => c.id === ch.id ? { ...c, name } : c))
                      }}
                    />
                    <span className="muted card-uid"> · {ch.role}</span>
                  </div>
                  {r ? (
                    <div className="readings-grid">
                      <div className="reading-stat">
                        <span className="stat-label">Voltage</span>
                        <span className={`stat-value ${mainsOk ? 'val-ok' : 'val-offline'}`}>
                          {r.v_avg.toFixed(1)} V
                        </span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Power</span>
                        <span className="stat-value">{r.p_avg.toFixed(0)} W</span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Current</span>
                        <span className="stat-value">{r.i_avg.toFixed(2)} A</span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Freq / PF</span>
                        <span className="stat-value muted">
                          {r.freq_avg.toFixed(1)} Hz · {r.pf_avg.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="no-reading">No data</div>
                  )}
                  {!mainsOk && r && (
                    <div className="mains-alert">⚠ Mains outage detected</div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          !showAcForm && <div className="empty-state-sm">No AC channels configured yet.</div>
        )}
      </section>

      {/* Battery cards */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">Batteries</h2>
          <button className="btn-ghost btn-sm" onClick={() => { setShowBatForm(s => !s); setBatError('') }}>
            {showBatForm ? 'Cancel' : '+ Add battery'}
          </button>
        </div>
        {showBatForm && (
          <form className="inline-form" onSubmit={handleAddBattery}>
            <input placeholder="Battery name (e.g. Bank A)" value={batName}
              onChange={e => setBatName(e.target.value)} />
            <input placeholder="Modbus addr" type="number" min="1" max="247" required
              value={batAddr} onChange={e => setBatAddr(e.target.value)} style={{ width: 120 }} />
            <select value={batShunt} onChange={e => setBatShunt(e.target.value)} title="Shunt rating">
              <option value="50">50 A shunt</option>
              <option value="100">100 A shunt</option>
              <option value="200">200 A shunt</option>
              <option value="300">300 A shunt</option>
            </select>
            <input placeholder="Nominal V (e.g. 12.0)" type="number" step="0.1" required
              value={batNominal} onChange={e => setBatNominal(e.target.value)} style={{ width: 120 }} />
            {batError && <span className="form-error">{batError}</span>}
            <button type="submit" className="btn-primary btn-sm" disabled={batBusy}>
              {batBusy ? 'Adding…' : 'Add'}
            </button>
          </form>
        )}
        {batteries.length > 0 ? (
          <div className="card-grid">
            {batteries.map(bat => {
              const r = dcReadings[bat.id]
              const nominal = parseFloat(bat.nominal_v)
              const { label: stateLabel, cls: stateCls } = r
                ? currentLabel(r.i_avg) : { label: 'Unknown', cls: 'badge-grey' }
              const hasAlarm = r && r.alarm > 0
              return (
                <div
                  key={bat.id}
                  className={`reading-card clickable ${selectedBattery?.id === bat.id ? 'card-selected' : ''} ${hasAlarm ? 'border-red' : ''}`}
                  onClick={() => { setSelectedBattery(bat); setSelectedChannel(null); setSelectedSensor(null) }}
                >
                  <div className="card-title">
                    <InlineEdit
                      value={bat.name || bat.battery_uid.split('-').pop()?.toUpperCase() || bat.battery_uid}
                      onSave={async (name) => {
                        await updateBattery(bat.id, { name })
                        setBatteries(prev => prev.map(b => b.id === bat.id ? { ...b, name } : b))
                      }}
                    />
                    <span className="muted card-uid"> · addr {bat.modbus_addr}</span>
                    <span className={`badge ${stateCls}`} style={{ float: 'right' }}>{stateLabel}</span>
                  </div>
                  {r ? (
                    <div className="readings-grid">
                      <div className="reading-stat">
                        <span className="stat-label">Voltage</span>
                        <span className={`stat-value ${voltageClass(r.v_avg, nominal)}`}>
                          {r.v_avg.toFixed(3)} V
                        </span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Current</span>
                        <span className={`stat-value ${r.i_avg < 0 ? 'val-orange' : 'val-ok'}`}>
                          {r.i_avg > 0 ? '+' : ''}{r.i_avg.toFixed(2)} A
                        </span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Power</span>
                        <span className="stat-value">{Math.abs(r.p_avg).toFixed(1)} W</span>
                      </div>
                      <div className="reading-stat">
                        <span className="stat-label">Energy</span>
                        <span className="stat-value muted">
                          {r.energy_wh !== undefined ? r.energy_wh.toFixed(1) : '—'} Wh
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="no-reading">No data</div>
                  )}
                  {hasAlarm && <div className="alarm-flag">⚠ Low voltage alarm</div>}
                </div>
              )
            })}
          </div>
        ) : (
          !showBatForm && <div className="empty-state-sm">No batteries configured yet.</div>
        )}
      </section>

      {/* RS485 Sensors */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">Sensors</h2>
          <button className="btn-ghost btn-sm" onClick={() => { setShowSensorForm(s => !s); setSensorError('') }}>
            {showSensorForm ? 'Cancel' : '+ Add sensor'}
          </button>
        </div>
        {showSensorForm && (
          <form className="inline-form" onSubmit={handleAddSensor}>
            <input placeholder="Name (e.g. Battery Room Env)" required value={sensorName}
              onChange={e => setSensorName(e.target.value)} />
            <select value={sensorType} onChange={e => setSensorType(e.target.value)}>
              <option value="temp_humidity">Temp / Humidity (XY-MD02)</option>
              <option value="gas_h2">Hydrogen gas (H₂)</option>
            </select>
            <input placeholder="Modbus addr" type="number" min="1" max="247" required
              value={sensorAddr} onChange={e => setSensorAddr(e.target.value)} style={{ width: 120 }} />
            {sensorError && <span className="form-error">{sensorError}</span>}
            <button type="submit" className="btn-primary btn-sm" disabled={sensorBusy}>
              {sensorBusy ? 'Adding…' : 'Add'}
            </button>
          </form>
        )}
        {sensors.length > 0 ? (
          <div className="card-grid">
            {sensors.map(s => {
              const r = sensorReadings[s.id]
              const isTH = s.sensor_type === 'temp_humidity'
              const isH2 = s.sensor_type === 'gas_h2'
              const h2Alarm = isH2 && r && (r.payload.alarm === true || Number(r.payload.ppm) > 50)
              return (
                <div key={s.id}
                  className={`reading-card clickable ${selectedSensor?.id === s.id ? 'card-selected' : ''} ${h2Alarm ? 'border-red' : 'border-grey'}`}
                  onClick={() => { setSelectedSensor(s); setSelectedBattery(null); setSelectedChannel(null) }}>
                  <div className="card-title">
                    <InlineEdit
                      value={s.name}
                      onSave={async (name) => {
                        await updateSensor(s.id, { name })
                        setSensors(prev => prev.map(x => x.id === s.id ? { ...x, name } : x))
                      }}
                    />
                    <span className="muted card-uid"> · {s.sensor_type} · addr {s.modbus_addr}</span>
                  </div>
                  {r ? (
                    <div className="readings-grid">
                      {isTH && <>
                        <div className="reading-stat">
                          <span className="stat-label">Temperature</span>
                          <span className="stat-value val-ok">
                            {Number(r.payload.temperature_c).toFixed(1)} °C
                          </span>
                        </div>
                        <div className="reading-stat">
                          <span className="stat-label">Humidity</span>
                          <span className="stat-value">
                            {Number(r.payload.humidity_pct).toFixed(1)} %
                          </span>
                        </div>
                      </>}
                      {isH2 && <>
                        <div className="reading-stat">
                          <span className="stat-label">H₂ concentration</span>
                          <span className={`stat-value ${h2Alarm ? 'val-warn' : 'val-ok'}`}>
                            {Number(r.payload.ppm).toFixed(0)} ppm
                          </span>
                        </div>
                        <div className="reading-stat">
                          <span className="stat-label">Alarm</span>
                          <span className={`stat-value ${r.payload.alarm ? 'val-warn' : 'val-ok'}`}>
                            {r.payload.alarm ? 'YES' : 'No'}
                          </span>
                        </div>
                      </>}
                    </div>
                  ) : (
                    <div className="no-reading">No data</div>
                  )}
                  {h2Alarm && <div className="alarm-flag">⚠ H₂ gas alarm!</div>}
                </div>
              )
            })}
          </div>
        ) : (
          !showSensorForm && <div className="empty-state-sm">No sensors configured yet.</div>
        )}
      </section>

      {/* Chart for selected item */}
      {selectedBattery && (
        <section className="section">
          <BatteryChart
            batteryId={selectedBattery.id}
            label={selectedBattery.name || selectedBattery.battery_uid}
          />
        </section>
      )}
      {selectedChannel && (
        <section className="section">
          <AcChannelChart
            channelId={selectedChannel.id}
            label={selectedChannel.name}
          />
        </section>
      )}
      {selectedSensor && (
        <section className="section">
          <SensorChart
            sensorId={selectedSensor.id}
            sensorType={selectedSensor.sensor_type}
            label={selectedSensor.name}
          />
        </section>
      )}

      {/* Events log */}
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">Events</h2>
          <label className="toggle-label" style={{ fontSize: '0.85rem', gap: '0.4rem', display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={eventsOpenOnly}
              onChange={e => {
                const open = e.target.checked
                setEventsOpenOnly(open)
                if (applianceId) {
                  listEvents({ appliance_id: applianceId, open_only: open, limit: 50 })
                    .then(setEvents).catch(() => {})
                }
              }}
            />
            Open only
          </label>
        </div>
        {events.length === 0 ? (
          <div className="empty-state-sm">No events recorded yet.</div>
        ) : (
          <table className="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Kind</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.map(ev => (
                <tr key={ev.id} className={ev.resolved_at ? '' : 'event-open'}>
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
                  <td>
                    {ev.resolved_at
                      ? <span className="badge badge-grey">Resolved</span>
                      : <span className="badge badge-orange">Open</span>
                    }
                  </td>
                  <td className="muted" style={{ fontSize: '0.8rem', maxWidth: 300, wordBreak: 'break-all' }}>
                    {ev.detail ? JSON.stringify(ev.detail) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
