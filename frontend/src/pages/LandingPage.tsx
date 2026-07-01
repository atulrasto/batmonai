import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api/client'
import './LandingPage.css'

const FEATURES = [
  {
    icon: '🔥',
    title: 'Fire & Thermal Runaway Prevention',
    desc: 'Continuous voltage and temperature monitoring triggers instant alerts when cells approach dangerous thresholds — stopping thermal runaway before it escalates into a fire.',
  },
  {
    icon: '💧',
    title: 'Electrolyte Depletion Detection',
    desc: 'Low water levels cause internal resistance spikes, heating, and irreversible plate damage. AI models detect these resistance patterns early and flag batteries needing water top-up.',
  },
  {
    icon: '🌡️',
    title: 'Ambient Temperature & Humidity',
    desc: 'Optional RS485 sensors on the same bus monitor battery room temperature and humidity — leading indicators of gassing, corrosion, and heat-related degradation.',
  },
  {
    icon: '☁️',
    title: '24/7 Cloud Surveillance',
    desc: 'Telemetry every 10 seconds, securely ingested over MQTT/TLS into a time-series database. Access live readings and months of history from any device, anywhere.',
  },
  {
    icon: '🤖',
    title: 'AI/ML Anomaly Detection',
    desc: 'Machine learning models learn your battery\'s normal charge/discharge signature. Subtle deviations — capacity fade, unexpected self-discharge, abnormal float current — are flagged automatically.',
  },
  {
    icon: '🔧',
    title: 'Predictive Maintenance',
    desc: 'Move from reactive to proactive: AI-generated maintenance windows, capacity trend graphs, and estimated remaining service life dramatically reduce unplanned replacements.',
  },
  {
    icon: '⚡',
    title: 'Inverter Efficiency Analytics',
    desc: 'Monitor AC input voltage, current, power factor, and frequency. Detect mains outages in real time, identify inverter inefficiency, and track energy consumption trends.',
  },
  {
    icon: '🚨',
    title: 'Hydrogen Gas Leak Detection',
    desc: 'Overcharging releases explosive hydrogen gas. Integrated H₂ sensors raise high-severity alerts the moment ppm levels exceed safe thresholds — protecting personnel and assets.',
  },
  {
    icon: '📊',
    title: 'Automated Reports & Alerts',
    desc: 'Daily PDF reports per battery and per inverter, delivered to your inbox. Webhook integrations push critical events into Slack, Teams, PagerDuty, or any ticketing system.',
  },
  {
    icon: '🏭',
    title: 'Multi-Site, Multi-Tenant',
    desc: 'Manage hundreds of battery strings across multiple sites from a single dashboard. Role-based access keeps each organisation\'s data strictly isolated with row-level security.',
  },
  {
    icon: '🔋',
    title: 'Battery Life Extension',
    desc: 'Proper charge/discharge management guided by real-time data can extend lead-acid battery life by 40–60%. The system recommends equalisation cycles and flags over-discharge events.',
  },
  {
    icon: '📡',
    title: 'Remote & Offline Resilient',
    desc: 'ESP32 gateways buffer telemetry locally during connectivity loss and replay it on reconnect. Store-and-forward architecture ensures no data gaps even in intermittent network conditions.',
  },
]

const INDUSTRIES = [
  { icon: '🖥️', name: 'Data Centers', desc: 'UPS backup health is mission-critical' },
  { icon: '🏥', name: 'Hospitals & Clinics', desc: 'Life-support power must never fail' },
  { icon: '📡', name: 'Telecom Towers', desc: 'Remote sites with no on-site staff' },
  { icon: '🏭', name: 'Manufacturing', desc: 'Production line power continuity' },
  { icon: '🏦', name: 'Banking & Finance', desc: 'Zero-downtime compliance requirement' },
  { icon: '🌞', name: 'Solar + Storage', desc: 'Battery health drives ROI' },
  { icon: '🚨', name: 'Emergency Services', desc: 'Mission-critical always-on power' },
  { icon: '🏗️', name: 'Construction Sites', desc: 'Remote power with no grid fallback' },
  { icon: '🛡️', name: 'Defence & Military', desc: 'Mission-critical power in field & base operations' },
]

export default function LandingPage() {
  const { user, loading } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' })
  const [status, setStatus] = useState<'idle' | 'sending' | 'ok' | 'err'>('idle')

  if (!loading && user) return <Navigate to="/dashboard" replace />

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm(p => ({ ...p, [field]: e.target.value }))
  }

  async function handleContact(e: React.FormEvent) {
    e.preventDefault()
    setStatus('sending')
    try {
      await api.post('/contact', form)
      setStatus('ok')
      setForm({ name: '', email: '', company: '', message: '' })
    } catch {
      setStatus('err')
    }
  }

  return (
    <div className="landing">

      {/* ── NAV ── */}
      <nav className="lnav">
        <div className="lnav-logo">⚡ batmonai</div>
        <div className="lnav-right">
          <div className="lnav-links">
            <a href="#features" className="lnav-link">Features</a>
            <a href="#industries" className="lnav-link">Industries</a>
            <a href="#contact" className="lnav-link">Contact</a>
          </div>
          <button className="btn-login-nav" onClick={() => nav('/login')}>Sign In</button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="hero-section">
        <div className="hero-bg" />
        <div className="hero-grid-bg" />
        <div className="hero-inner">
          <div className="hero-content">
            <div className="hero-badge">
              <span className="hero-badge-dot" />
              AI-Powered Battery Intelligence
            </div>
            <h1 className="hero-h1">
              Never Let a<br />
              <span className="hero-accent">Battery Failure</span><br />
              Surprise You Again
            </h1>
            <p className="hero-sub">
              Continuous 24/7 cloud monitoring of lead-acid batteries and inverters.
              Detect anomalies before they become disasters. Prevent fires. Extend
              battery life. Protect your operations and people.
            </p>
            <div className="hero-cta">
              <button className="btn-hero-primary" onClick={() => nav('/login')}>
                Access Dashboard →
              </button>
              <a href="#contact" className="btn-hero-ghost">Talk to Sales</a>
            </div>
            <div className="hero-stats">
              <div className="hstat">
                <span className="hstat-val">10s</span>
                <span className="hstat-label">Telemetry Interval</span>
              </div>
              <div className="hstat-div" />
              <div className="hstat">
                <span className="hstat-val">24/7</span>
                <span className="hstat-label">Cloud Monitoring</span>
              </div>
              <div className="hstat-div" />
              <div className="hstat">
                <span className="hstat-val">AI</span>
                <span className="hstat-label">Anomaly Detection</span>
              </div>
              <div className="hstat-div" />
              <div className="hstat">
                <span className="hstat-val">+40%</span>
                <span className="hstat-label">Battery Life Gain</span>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <div className="battery-art">
              <div className="bat-tip" />
              <div className="bat-body">
                <div className="bat-fill" />
                <div className="bat-scan" />
                <div className="bat-label">⚡ LIVE</div>
                <div className="bat-pct">72%</div>
              </div>
            </div>
            <div className="bat-metrics">
              <div className="bat-metric">
                <span>Voltage</span><span>12.84 V</span>
              </div>
              <div className="bat-metric">
                <span>Current</span><span>−5.20 A</span>
              </div>
              <div className="bat-metric green">
                <span>Status</span><span>✓ Normal</span>
              </div>
              <div className="bat-metric green">
                <span>Temp</span><span>34 °C</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── PROBLEM STATS ── */}
      <section className="problem-section">
        <div className="lcontainer">
          <div className="lsection-label">The Problem</div>
          <h2 className="lsection-h2">Battery Failures Are Costly — and Preventable</h2>
          <div className="problem-grid">
            <div className="problem-card danger">
              <div className="prob-icon">🔥</div>
              <div className="prob-stat">40%</div>
              <p className="prob-text">
                of industrial battery fires originate from overcharging, thermal runaway, or
                electrolyte depletion — all detectable hours or days in advance with continuous monitoring.
              </p>
            </div>
            <div className="problem-card warn">
              <div className="prob-icon">⏱</div>
              <div className="prob-stat">$5,600/min</div>
              <p className="prob-text">
                average cost of data center downtime caused by failed backup power.
                A single UPS battery failure during a mains outage can cost millions.
              </p>
            </div>
            <div className="problem-card info">
              <div className="prob-icon">🔋</div>
              <div className="prob-stat">30–50%</div>
              <p className="prob-text">
                shorter battery service life when cells operate without water-level, temperature,
                and charge cycle management — all invisible without IoT monitoring.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="features-section" id="features">
        <div className="lcontainer">
          <div className="lsection-label">What We Monitor</div>
          <h2 className="lsection-h2">Complete Battery & Inverter Intelligence</h2>
          <div className="features-grid">
            {FEATURES.map(f => (
              <div className="feature-card" key={f.title}>
                <span className="feat-icon">{f.icon}</span>
                <h3 className="feat-title">{f.title}</h3>
                <p className="feat-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="how-section">
        <div className="lcontainer">
          <div className="lsection-label">Simple Setup</div>
          <h2 className="lsection-h2">Up and Running in Hours, Not Weeks</h2>
          <div className="steps-row">
            <div className="step-card">
              <div className="step-num">01</div>
              <h3>Install Gateway</h3>
              <p>
                Clip PZEM-017 sensors on each battery string and a PZEM-004T on the AC line.
                Daisy-chain them over RS485. Connect the compact ESP32 gateway to your WiFi.
              </p>
            </div>
            <div className="step-card">
              <div className="step-num">02</div>
              <h3>Provision & Connect</h3>
              <p>
                Flash the device with your site credentials using our web provisioning tool.
                It authenticates and publishes encrypted telemetry to the cloud every 10 seconds.
              </p>
            </div>
            <div className="step-card">
              <div className="step-num">03</div>
              <h3>Monitor & Act</h3>
              <p>
                View live readings, historical charts, and AI-generated alerts on your dashboard.
                Receive instant email or webhook notifications before problems escalate.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── INDUSTRIES ── */}
      <section className="industries-section" id="industries">
        <div className="lcontainer">
          <div className="lsection-label">Built For</div>
          <h2 className="lsection-h2">Critical Operations That Can't Afford Downtime</h2>
          <div className="industries-grid">
            {INDUSTRIES.map(i => (
              <div className="industry-card" key={i.name}>
                <span className="ind-icon">{i.icon}</span>
                <span className="ind-name">{i.name}</span>
                <span className="ind-desc">{i.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CONTACT ── */}
      <section className="contact-section" id="contact">
        <div className="lcontainer">
          <div className="contact-grid">
            <div className="contact-left">
              <div className="lsection-label">Get In Touch</div>
              <h2 className="lsection-h2">Ready to Protect Your Batteries?</h2>
              <p className="contact-sub">
                Talk to our team about your battery fleet. We'll design a monitoring
                solution tailored to your infrastructure and operational requirements.
              </p>
              <div className="contact-points">
                {[
                  'Free initial consultation',
                  'Custom deployment support',
                  '24/7 technical assistance',
                  'Training for your operations team',
                  'Integration with existing SCADA / BMS systems',
                ].map(p => (
                  <div className="cpoint" key={p}>
                    <span className="cpoint-check">✓</span> {p}
                  </div>
                ))}
              </div>
            </div>

            <form className="contact-form" onSubmit={handleContact}>
              <div className="cf-row">
                <input
                  className="cf-input" placeholder="Your Name *" required
                  value={form.name} onChange={set('name')}
                />
                <input
                  className="cf-input" type="email" placeholder="Email Address *" required
                  value={form.email} onChange={set('email')}
                />
              </div>
              <input
                className="cf-input" placeholder="Company / Organisation"
                value={form.company} onChange={set('company')}
              />
              <textarea
                className="cf-textarea"
                placeholder="Tell us about your battery infrastructure — number of batteries, sites, current monitoring setup, and what you'd like to achieve..."
                required
                value={form.message} onChange={set('message')}
              />
              <button className="btn-cf-submit" type="submit" disabled={status === 'sending'}>
                {status === 'sending' ? 'Sending…' : 'Send Message →'}
              </button>
              {status === 'ok' && (
                <div className="cf-ok">✓ Message sent — our team will be in touch within 24 hours.</div>
              )}
              {status === 'err' && (
                <div className="cf-err">Failed to send. Please try again or email us directly.</div>
              )}
            </form>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-logo">⚡ batmonai</div>
          <div className="footer-tagline">AI-Powered Battery & Inverter Monitoring System</div>
          <span className="footer-copy">© {new Date().getFullYear()} energymonai.com</span>
          <button
            className="btn-login-nav"
            style={{ marginLeft: 'auto' }}
            onClick={() => nav('/login')}
          >
            Sign In →
          </button>
        </div>
      </footer>
    </div>
  )
}
