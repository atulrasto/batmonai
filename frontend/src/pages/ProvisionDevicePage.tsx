/**
 * Provision Device — available to ALL authenticated users.
 *
 * Sends WiFi + identity config to an already-flashed ESP32 via USB serial
 * (Web Serial API).  Works in Chrome / Edge only.
 *
 * Flow:
 *   1. Select appliance  →  auto-fills appliance_uid
 *   2. Regenerate device secret  (stores new hash in DB, shows plaintext once)
 *   3. Enter WiFi SSID + password
 *   4. Connect USB → provision → done
 */
import { useEffect, useState, useRef } from 'react'
import { Transport } from 'esptool-js'
import type { Appliance } from '../types'
import { listAppliances, regenerateSecret } from '../api/resources'
import { useAuth } from '../context/AuthContext'

interface ProvConfig {
  wifi_ssid: string
  wifi_pass: string
  appliance_uid: string
  device_secret: string
  broker_host: string
  broker_port: number
  tls_insecure: boolean
}

function hasWebSerial(): boolean {
  return typeof navigator !== 'undefined' && 'serial' in navigator
}

// Wait for a line containing `marker` from the device within `timeoutMs`.
// Returns the full accumulated text.
async function waitForMarker(
  transport: Transport,
  marker: string,
  timeoutMs: number,
  onLine: (s: string) => void
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
      text.split('\n').forEach(l => l.trim() && onLine(l.trim()))
      if (buf.includes(marker)) { found = true; stop = true }
    },
    () => stop,
  )

  clearTimeout(timer)
  return { text: buf, ok: found }
}

export default function ProvisionDevicePage() {
  const { user: _user } = useAuth()

  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [loading, setLoading] = useState(true)

  // Form state
  const [applianceId, setApplianceId] = useState('')
  const [applianceUid, setApplianceUid] = useState('')
  const [deviceSecret, setDeviceSecret] = useState('')
  const [secretGenerated, setSecretGenerated] = useState(false)
  const [wifiSsid, setWifiSsid] = useState('')
  const [wifiPass, setWifiPass] = useState('')
  const [brokerHost, setBrokerHost] = useState('batmon.energymonai.com')
  const [brokerPort, setBrokerPort] = useState(8883)
  const [tlsInsecure, setTlsInsecure] = useState(false)

  // Progress
  const [step, setStep] = useState<'idle' | 'provisioning' | 'done' | 'error'>('idle')
  const [log, setLog] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)

  const addLog = (msg: string) =>
    setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])

  useEffect(() => {
    listAppliances()
      .then(setAppliances)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  function handleApplianceChange(id: string) {
    setApplianceId(id)
    const a = appliances.find(x => x.id === id)
    setApplianceUid(a?.appliance_uid ?? '')
    setDeviceSecret('')
    setSecretGenerated(false)
  }

  async function handleRegenSecret() {
    if (!applianceId) return
    try {
      const res = await regenerateSecret(applianceId)
      setDeviceSecret(res.device_secret)
      setSecretGenerated(true)
    } catch {
      alert('Failed to regenerate secret')
    }
  }

  async function handleProvision() {
    if (!hasWebSerial()) {
      alert('Web Serial API is not supported. Please use Chrome or Edge.')
      return
    }
    if (!applianceId || !applianceUid || !deviceSecret || !wifiSsid) {
      alert('Fill in all required fields and regenerate the device secret.')
      return
    }

    setStep('provisioning')
    setLog([])

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const serial = (navigator as any).serial as { requestPort(): Promise<unknown> }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let port: any = null
    let transport: Transport | null = null

    try {
      addLog('Select the ESP32 serial port…')
      port = await serial.requestPort()
      transport = new Transport(port)
      await transport.connect(115200)
      addLog('Serial port connected at 115200 baud')

      const config: ProvConfig = {
        wifi_ssid: wifiSsid,
        wifi_pass: wifiPass,
        appliance_uid: applianceUid,
        device_secret: deviceSecret,
        broker_host: brokerHost,
        broker_port: brokerPort,
        tls_insecure: tlsInsecure,
      }

      addLog('Waiting for device to enter provisioning mode…')
      addLog('  → Hold BOOT button, press RESET, release BOOT if needed.')

      const { ok: ready } = await waitForMarker(transport, 'PROV:READY', 20000, addLog)
      if (!ready) {
        addLog('ERROR: Device did not signal PROV:READY within 20 s')
        setStep('error')
        return
      }

      addLog('Device ready — sending config…')
      const enc = new TextEncoder()
      await transport.write(enc.encode(JSON.stringify(config) + '\n'))

      const { text: result } = await waitForMarker(transport, 'PROV:', 10000, addLog)

      if (result.includes('PROV:OK')) {
        addLog('Device provisioned successfully! It will restart and connect.')
        setStep('done')
      } else {
        const m = result.match(/PROV:ERR:(.+)/)
        addLog(`ERROR: ${m ? m[1] : 'Unknown error from device'}`)
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

  if (loading) return <div className="page-loading">Loading…</div>

  if (!hasWebSerial()) {
    return (
      <div className="page">
        <h1>Provision Device</h1>
        <div className="card" style={{ borderColor: '#f59e0b', background: '#fffbeb' }}>
          <strong>Browser not supported.</strong> Web Serial API requires Chrome or Edge (desktop).
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Provision Device</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>
          Send WiFi &amp; identity config to an ESP32 over USB (Chrome / Edge only)
        </p>
      </div>

      <div className="card" style={{ maxWidth: 560 }}>
        {/* Step 1 — Appliance */}
        <section className="form-section">
          <h3>1. Select Appliance</h3>
          <label>Appliance
            <select
              value={applianceId}
              onChange={e => handleApplianceChange(e.target.value)}
              disabled={step === 'provisioning'}
            >
              <option value="">— choose —</option>
              {appliances.map(a => (
                <option key={a.id} value={a.id}>
                  {a.appliance_uid} {a.name ? `(${a.name})` : ''}
                </option>
              ))}
            </select>
          </label>
          {applianceUid && (
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
              UID: <code>{applianceUid}</code>
            </p>
          )}
        </section>

        {/* Step 2 — Device secret */}
        <section className="form-section">
          <h3>2. Device Secret</h3>
          <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: 0 }}>
            Generate a new secret — this updates the broker password for this appliance
            and is shown once only.
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type={secretGenerated ? 'text' : 'password'}
              value={deviceSecret}
              onChange={e => setDeviceSecret(e.target.value)}
              placeholder="Click Generate or enter existing"
              disabled={step === 'provisioning'}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn-primary"
              onClick={handleRegenSecret}
              disabled={!applianceId || step === 'provisioning'}
              style={{ whiteSpace: 'nowrap' }}
            >
              Generate
            </button>
          </div>
          {secretGenerated && (
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#059669' }}>
              New secret generated — copy it if needed. It will be written to the device.
            </p>
          )}
        </section>

        {/* Step 3 — WiFi */}
        <section className="form-section">
          <h3>3. WiFi Credentials</h3>
          <label>WiFi SSID *
            <input
              type="text"
              value={wifiSsid}
              onChange={e => setWifiSsid(e.target.value)}
              placeholder="Network name"
              disabled={step === 'provisioning'}
            />
          </label>
          <label>WiFi Password
            <input
              type="password"
              value={wifiPass}
              onChange={e => setWifiPass(e.target.value)}
              placeholder="Leave blank for open network"
              disabled={step === 'provisioning'}
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
              <input value={brokerHost} onChange={e => setBrokerHost(e.target.value)} disabled={step === 'provisioning'} />
            </label>
            <label>Broker Port
              <input type="number" value={brokerPort} onChange={e => setBrokerPort(+e.target.value)} disabled={step === 'provisioning'} />
            </label>
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={tlsInsecure} onChange={e => setTlsInsecure(e.target.checked)} disabled={step === 'provisioning'} />
              Skip TLS certificate validation (dev only)
            </label>
          </div>
        </details>

        {/* Action */}
        <button
          className="btn-primary"
          style={{ width: '100%' }}
          onClick={handleProvision}
          disabled={step === 'provisioning' || !applianceId || !deviceSecret || !wifiSsid}
        >
          {step === 'provisioning' ? 'Provisioning…' : 'Connect & Provision'}
        </button>

        {step === 'done' && (
          <div className="alert-success" style={{ marginTop: 12 }}>
            Device provisioned successfully. It will reboot and connect to the broker.
          </div>
        )}
        {step === 'error' && (
          <div className="form-error" style={{ marginTop: 12 }}>
            Provisioning failed. See log below.
          </div>
        )}
      </div>

      {/* Serial log */}
      {log.length > 0 && (
        <div className="card" style={{ marginTop: 16, maxWidth: 560 }}>
          <h4 style={{ margin: '0 0 8px' }}>Serial log</h4>
          <div
            ref={logRef}
            style={{
              background: '#111827', color: '#d1fae5',
              fontFamily: 'monospace', fontSize: '0.78rem',
              padding: 12, borderRadius: 6, maxHeight: 220, overflowY: 'auto',
            }}
          >
            {log.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: 16, maxWidth: 560, fontSize: '0.82rem', color: '#6b7280' }}>
        <strong>Instructions:</strong>
        <ol style={{ margin: '8px 0 0', paddingLeft: 20 }}>
          <li>Connect the ESP32 via USB to this computer.</li>
          <li>Select your appliance and generate a new device secret.</li>
          <li>Enter the WiFi SSID and password for the device's install location.</li>
          <li>Click <strong>Connect &amp; Provision</strong> and select the COM port.</li>
          <li>If the device is already running firmware: hold BOOT, press RESET, release BOOT to enter provisioning mode.</li>
          <li>Wait for "Device provisioned successfully" — the device will reboot and connect.</li>
        </ol>
      </div>
    </div>
  )
}
