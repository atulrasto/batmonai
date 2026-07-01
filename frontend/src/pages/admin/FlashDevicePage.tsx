/**
 * Flash Device — SUPERUSER ONLY (factory use at Rastotel).
 *
 * 1. Select a pre-built firmware release served from the API.
 * 2. Select the appliance to associate with this unit.
 * 3. Enter site WiFi credentials (unique per device install location).
 * 4. Click Connect & Flash:
 *    a) esptool-js flashes the firmware over USB serial.
 *    b) After flash, the device boots into provisioning mode.
 *    c) App sends identity + WiFi config over the same serial port.
 *    d) Device writes to NVS and restarts.
 *
 * Requires Chrome or Edge (Web Serial API).
 */
import { useEffect, useState, useRef } from 'react'
import { ESPLoader, Transport } from 'esptool-js'
import type { Appliance, Client, Site } from '../../types'
import { listAppliances, listClients, listSites, regenerateSecret } from '../../api/resources'
import { listReleases, downloadFirmwareFile } from '../../api/firmware'
import type { FirmwareRelease } from '../../api/firmware'

interface ProvConfig {
  wifi_ssid: string
  wifi_pass: string
  appliance_uid: string
  device_secret: string
  broker_host: string
  broker_port: number
  tls_insecure: boolean
}

type Step = 'config' | 'flashing' | 'provisioning' | 'done' | 'error'

function hasWebSerial(): boolean {
  return typeof navigator !== 'undefined' && 'serial' in navigator
}

async function waitForMarker(
  transport: Transport,
  marker: string,
  timeoutMs: number,
  onText: (s: string) => void,
): Promise<{ text: string; ok: boolean }> {
  const dec = new TextDecoder()
  let buf = ''
  let stop = false
  let found = false
  const timer = setTimeout(() => { stop = true }, timeoutMs)
  await transport.rawRead(
    (chunk) => {
      const text = dec.decode(chunk)
      buf += text
      text.split('\n').forEach(l => l.trim() && onText(l.trim()))
      if (buf.includes(marker)) { found = true; stop = true }
    },
    () => stop,
  )
  clearTimeout(timer)
  return { text: buf, ok: found }
}

export default function FlashDevicePage() {
  const [releases, setReleases] = useState<FirmwareRelease[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [loading, setLoading] = useState(true)

  // Selection
  const [selectedVersion, setSelectedVersion] = useState('')
  const [selectedClientId, setSelectedClientId] = useState('')
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [selectedApplianceId, setSelectedApplianceId] = useState('')
  const [applianceUid, setApplianceUid] = useState('')
  const [deviceSecret, setDeviceSecret] = useState('')
  const [secretReady, setSecretReady] = useState(false)

  // WiFi
  const [wifiSsid, setWifiSsid] = useState('')
  const [wifiPass, setWifiPass] = useState('')
  const [brokerHost, setBrokerHost] = useState('batmon.energymonai.com')
  const [brokerPort, setBrokerPort] = useState(8883)
  const [tlsInsecure, setTlsInsecure] = useState(false)

  // Progress
  const [step, setStep] = useState<Step>('config')
  const [flashProgress, setFlashProgress] = useState(0)
  const [log, setLog] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)

  const addLog = (msg: string) =>
    setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])

  useEffect(() => {
    Promise.all([listReleases(), listClients(), listSites(), listAppliances()])
      .then(([r, c, s, a]) => {
        setReleases(r.filter(x => x.ready))
        setClients(c)
        setSites(s)
        setAppliances(a)
        if (r.filter(x => x.ready).length > 0) setSelectedVersion(r[0].version)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  function handleClientChange(id: string) {
    setSelectedClientId(id)
    setSelectedSiteId('')
    setSelectedApplianceId('')
    setApplianceUid('')
    setDeviceSecret('')
    setSecretReady(false)
  }

  function handleSiteChange(id: string) {
    setSelectedSiteId(id)
    setSelectedApplianceId('')
    setApplianceUid('')
    setDeviceSecret('')
    setSecretReady(false)
  }

  function handleApplianceChange(id: string) {
    setSelectedApplianceId(id)
    const a = appliances.find(x => x.id === id)
    setApplianceUid(a?.appliance_uid ?? '')
    setDeviceSecret('')
    setSecretReady(false)
  }

  async function handleRegenSecret() {
    if (!selectedApplianceId) return
    try {
      const res = await regenerateSecret(selectedApplianceId)
      setDeviceSecret(res.device_secret)
      setSecretReady(true)
    } catch {
      alert('Failed to regenerate device secret')
    }
  }

  const filteredSites = selectedClientId
    ? sites.filter(s => s.client_id === selectedClientId)
    : sites

  const filteredAppliances = selectedSiteId
    ? appliances.filter(a => a.site_id === selectedSiteId)
    : selectedClientId
    ? appliances.filter(a => a.client_id === selectedClientId)
    : appliances

  async function handleFlash() {
    if (!hasWebSerial()) {
      alert('Web Serial API requires Chrome or Edge (desktop).')
      return
    }
    if (!selectedVersion || !selectedApplianceId || !deviceSecret || !wifiSsid) {
      alert('Fill in all required fields and generate a device secret.')
      return
    }

    const release = releases.find(r => r.version === selectedVersion)
    if (!release) return

    setStep('flashing')
    setLog([])
    setFlashProgress(0)

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const serial = (navigator as any).serial as { requestPort(): Promise<unknown> }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let port: any = null
    let transport: Transport | null = null

    try {
      addLog('Select the ESP32 USB serial port…')
      port = await serial.requestPort()
      transport = new Transport(port)

      // ── Step A: Flash firmware ──────────────────────────────────────────────
      addLog(`Downloading firmware ${selectedVersion}…`)

      // Download all binary files in parallel
      const fileData = await Promise.all(
        release.files.map(f =>
          downloadFirmwareFile(selectedVersion, f.path).then(data => ({
            data,
            address: parseInt(f.address, 16),
            name: f.path,
          }))
        )
      )
      addLog(`Downloaded ${fileData.length} files (${fileData.reduce((s, f) => s + f.data.length, 0)} bytes total)`)

      const terminal = {
        clean: () => {},
        writeLine: (s: string) => addLog(s),
        write: (s: string) => addLog(s),
      }

      const loader = new ESPLoader({ transport, baudrate: 921600, terminal })

      addLog('Connecting to ESP32 ROM bootloader…')
      addLog('  → Hold BOOT, press RESET, release BOOT if not auto-detected.')

      const chip = await loader.main()
      addLog(`Connected: ${chip}`)

      addLog('Flashing firmware…')
      const totalBytes = fileData.reduce((s, f) => s + f.data.length, 0)
      let writtenTotal = 0

      await loader.writeFlash({
        fileArray: fileData.map(f => ({ data: f.data, address: f.address })),
        flashSize: 'keep',
        flashMode: 'keep',
        flashFreq: 'keep',
        eraseAll: false,
        compress: true,
        reportProgress: (fileIndex: number, written: number, total: number) => {
          const prevBytes = fileData.slice(0, fileIndex).reduce((s, f) => s + f.data.length, 0)
          writtenTotal = prevBytes + written
          const pct = Math.round((writtenTotal / totalBytes) * 100)
          setFlashProgress(pct)
          addLog(`${fileData[fileIndex].name}: ${written}/${total} bytes (${pct}%)`)
        },
      })

      setFlashProgress(100)
      addLog('Flash complete!')
      await loader.after()
      addLog('Device reset — booting firmware…')

      // ── Step B: Provision ───────────────────────────────────────────────────
      setStep('provisioning')
      addLog('Waiting for provisioning prompt (15 s)…')

      const config: ProvConfig = {
        wifi_ssid: wifiSsid,
        wifi_pass: wifiPass,
        appliance_uid: applianceUid,
        device_secret: deviceSecret,
        broker_host: brokerHost,
        broker_port: brokerPort,
        tls_insecure: tlsInsecure,
      }

      const { ok: ready } = await waitForMarker(transport, 'PROV:READY', 15000, addLog)
      if (!ready) {
        addLog('ERROR: Device did not send PROV:READY — check serial monitor or re-provision manually.')
        setStep('error')
        return
      }

      addLog('Sending config to device…')
      const enc = new TextEncoder()
      await transport.write(enc.encode(JSON.stringify(config) + '\n'))

      const { text: result } = await waitForMarker(transport, 'PROV:', 10000, addLog)

      if (result.includes('PROV:OK')) {
        addLog('Provisioned! Device will restart and connect to broker.')
        setStep('done')
      } else {
        const m = result.match(/PROV:ERR:(.+)/)
        addLog(`Provisioning error: ${m ? m[1] : 'Unknown'}`)
        setStep('error')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`ERROR: ${msg}`)
      setStep('error')
    } finally {
      try { await transport?.disconnect() } catch { /* ignore */ }
    }
  }

  function handleReset() {
    setStep('config')
    setLog([])
    setFlashProgress(0)
    setDeviceSecret('')
    setSecretReady(false)
  }

  if (!hasWebSerial()) {
    return (
      <div className="page">
        <h1>Flash Device</h1>
        <div className="card" style={{ borderColor: '#f59e0b' }}>
          <strong>Browser not supported.</strong> Web Serial API requires Chrome or Edge (desktop).
        </div>
      </div>
    )
  }

  if (loading) return <div className="page-loading">Loading…</div>

  const busy = step === 'flashing' || step === 'provisioning'

  return (
    <div className="page">
      <div className="page-header">
        <h1>Flash Device</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>
          Factory firmware flash + provisioning — Chrome / Edge only
        </p>
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* Config panel */}
        <div className="card" style={{ flex: '1 1 480px', maxWidth: 560 }}>

          {/* Firmware version */}
          <section className="form-section">
            <h3>1. Firmware Version</h3>
            {releases.length === 0 ? (
              <p style={{ color: '#ef4444' }}>
                No ready releases found. Build firmware and copy binaries to
                <code> firmware/releases/v*/</code>.
              </p>
            ) : (
              <label>Release
                <select
                  value={selectedVersion}
                  onChange={e => setSelectedVersion(e.target.value)}
                  disabled={busy}
                >
                  {releases.map(r => (
                    <option key={r.version} value={r.version}>
                      {r.version} — {r.description}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </section>

          {/* Appliance selection */}
          <section className="form-section">
            <h3>2. Appliance</h3>
            <label>Client
              <select value={selectedClientId} onChange={e => handleClientChange(e.target.value)} disabled={busy}>
                <option value="">— all clients —</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Site
              <select value={selectedSiteId} onChange={e => handleSiteChange(e.target.value)} disabled={busy}>
                <option value="">— all sites —</option>
                {filteredSites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>Appliance *
              <select value={selectedApplianceId} onChange={e => handleApplianceChange(e.target.value)} disabled={busy}>
                <option value="">— choose appliance —</option>
                {filteredAppliances.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.appliance_uid}{a.name ? ` (${a.name})` : ''}
                  </option>
                ))}
              </select>
            </label>
            {applianceUid && (
              <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
                UID: <code>{applianceUid}</code>
              </p>
            )}
          </section>

          {/* Device secret */}
          <section className="form-section">
            <h3>3. Device Secret</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type={secretReady ? 'text' : 'password'}
                value={deviceSecret}
                onChange={e => { setDeviceSecret(e.target.value); setSecretReady(false) }}
                placeholder="Click Generate new secret"
                disabled={busy}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn-primary"
                onClick={handleRegenSecret}
                disabled={!selectedApplianceId || busy}
                style={{ whiteSpace: 'nowrap' }}
              >
                Generate
              </button>
            </div>
            {secretReady && (
              <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#059669' }}>
                New secret generated. It will be written to this device.
              </p>
            )}
          </section>

          {/* WiFi */}
          <section className="form-section">
            <h3>4. WiFi (at install location)</h3>
            <label>WiFi SSID *
              <input
                type="text"
                value={wifiSsid}
                onChange={e => setWifiSsid(e.target.value)}
                placeholder="Network name"
                disabled={busy}
              />
            </label>
            <label>WiFi Password
              <input
                type="password"
                value={wifiPass}
                onChange={e => setWifiPass(e.target.value)}
                placeholder="Leave blank for open network"
                disabled={busy}
              />
            </label>
          </section>

          {/* Advanced */}
          <details style={{ marginBottom: 16 }}>
            <summary style={{ cursor: 'pointer', color: '#6b7280', fontSize: '0.85rem' }}>
              Advanced (broker settings)
            </summary>
            <div style={{ paddingTop: 8 }}>
              <label>Broker Host
                <input value={brokerHost} onChange={e => setBrokerHost(e.target.value)} disabled={busy} />
              </label>
              <label>Broker Port
                <input type="number" value={brokerPort} onChange={e => setBrokerPort(+e.target.value)} disabled={busy} />
              </label>
              <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" checked={tlsInsecure} onChange={e => setTlsInsecure(e.target.checked)} disabled={busy} />
                Skip TLS certificate validation (dev only)
              </label>
            </div>
          </details>

          {/* Flash progress */}
          {(step === 'flashing') && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4 }}>
                <span>Flashing firmware…</span>
                <span>{flashProgress}%</span>
              </div>
              <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8 }}>
                <div
                  style={{
                    width: `${flashProgress}%`, height: '100%',
                    background: '#3b82f6', borderRadius: 4,
                    transition: 'width 0.2s',
                  }}
                />
              </div>
            </div>
          )}

          {step === 'provisioning' && (
            <div style={{ marginBottom: 12, color: '#d97706', fontSize: '0.85rem' }}>
              Provisioning — sending config to device…
            </div>
          )}

          {step === 'done' && (
            <div className="alert-success" style={{ marginBottom: 12 }}>
              Device flashed &amp; provisioned successfully!
            </div>
          )}
          {step === 'error' && (
            <div className="form-error" style={{ marginBottom: 12 }}>
              Failed. See log for details.
            </div>
          )}

          {/* Buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-primary"
              style={{ flex: 1 }}
              onClick={handleFlash}
              disabled={busy || step === 'done' || releases.length === 0 || !selectedApplianceId || !deviceSecret || !wifiSsid}
            >
              {busy ? (step === 'flashing' ? `Flashing… ${flashProgress}%` : 'Provisioning…') : 'Connect & Flash'}
            </button>
            {(step === 'done' || step === 'error') && (
              <button className="btn-ghost" onClick={handleReset}>
                Flash another
              </button>
            )}
          </div>
        </div>

        {/* Log panel */}
        <div className="card" style={{ flex: '1 1 300px', maxWidth: 480 }}>
          <h4 style={{ margin: '0 0 8px' }}>Serial log</h4>
          <div
            ref={logRef}
            style={{
              background: '#111827', color: '#d1fae5',
              fontFamily: 'monospace', fontSize: '0.77rem',
              padding: 12, borderRadius: 6,
              minHeight: 160, maxHeight: 420, overflowY: 'auto',
            }}
          >
            {log.length === 0
              ? <span style={{ color: '#4b5563' }}>Log will appear here…</span>
              : log.map((l, i) => <div key={i}>{l}</div>)
            }
          </div>

          <div style={{ marginTop: 16, fontSize: '0.8rem', color: '#6b7280' }}>
            <strong>Instructions:</strong>
            <ol style={{ margin: '6px 0 0', paddingLeft: 18, lineHeight: 1.6 }}>
              <li>Select firmware version, appliance, and generate secret.</li>
              <li>Enter WiFi credentials for the device install site.</li>
              <li>Connect ESP32 via USB.</li>
              <li>Click <strong>Connect &amp; Flash</strong> → select COM port.</li>
              <li>Hold <strong>BOOT</strong>, press <strong>RESET</strong>, release <strong>BOOT</strong> when prompted.</li>
              <li>Wait — firmware flashes then device auto-provisions.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}
