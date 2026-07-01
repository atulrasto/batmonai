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
      <button
        className="hamburger"
        onClick={() => setSidebarOpen(o => !o)}
        aria-label="Toggle menu"
      >
        {sidebarOpen ? '✕' : '☰'}
      </button>

      <div
        className={`sidebar-overlay${sidebarOpen ? ' open' : ''}`}
        onClick={closeMenu}
      />

      <nav className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <Link to="/" className="sidebar-logo">⚡ batmonai</Link>
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
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="user-email">{user?.email}</span>
            <span className={`role-badge ${isSuperuser ? 'role-su' : 'role-client'}`}>
              {isSuperuser ? 'admin' : 'client'}
            </span>
          </div>
          <Link to="/" className="home-link">← Public site</Link>
          <button className="btn-ghost logout-btn" onClick={handleLogout}>Sign out</button>
        </div>
      </nav>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
