import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  function handleLogout() {
    logout()
    nav('/login', { replace: true })
  }

  function closeMenu() {
    setSidebarOpen(false)
  }

  const isSuperuser = user?.role === 'superuser'

  return (
    <div className="app-shell">

      {/* ── Fixed top bar — always visible ── */}
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="hamburger-topbar"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Toggle menu"
          >
            {sidebarOpen ? '✕' : '☰'}
          </button>
          <Link to="/" className="topbar-logo">⚡ batmonai</Link>
        </div>
        <div className="topbar-right">
          <Link to="/account" className="topbar-email topbar-account-link" title="My Account">
            {user?.email}
          </Link>
          <span className={`role-badge ${isSuperuser ? 'role-su' : 'role-client'}`}>
            {isSuperuser ? 'admin' : 'client'}
          </span>
          <Link to="/account" className="btn-ghost btn-sm topbar-account-btn">My Account</Link>
          <Link to="/" className="topbar-home-link">← Public site</Link>
          <button className="btn-ghost btn-sm" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      {/* ── Below topbar: sidebar + content ── */}
      <div className="app-body">
        <div
          className={`sidebar-overlay${sidebarOpen ? ' open' : ''}`}
          onClick={closeMenu}
        />

        <nav className={`sidebar${sidebarOpen ? ' open' : ''}`}>
          <div className="sidebar-links">
            <NavLink to="/dashboard" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
              Dashboard
            </NavLink>
            <NavLink to="/sites" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
              Sites
            </NavLink>
            {isSuperuser && (
              <>
                <NavLink to="/admin/clients" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
                  Clients
                </NavLink>
                <NavLink to="/admin/flash-device" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
                  Flash Device
                </NavLink>
              </>
            )}
            <NavLink to="/reports" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
              Reports
            </NavLink>
            <NavLink to="/provision-device" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} onClick={closeMenu}>
              Provision Device
            </NavLink>
          </div>
        </nav>

        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
