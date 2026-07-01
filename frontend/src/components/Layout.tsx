import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()

  function handleLogout() {
    logout()
    nav('/login', { replace: true })
  }

  const isSuperuser = user?.role === 'superuser'

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="sidebar-logo">⚡ batmonai</div>
        <div className="sidebar-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Dashboard
          </NavLink>
          <NavLink to="/sites" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Sites
          </NavLink>
          {isSuperuser && (
            <>
              <NavLink to="/admin/clients" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                Clients
              </NavLink>
              <NavLink to="/admin/flash-device" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                Flash Device
              </NavLink>
            </>
          )}
          <NavLink to="/reports" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Reports
          </NavLink>
          <NavLink to="/provision-device" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
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
          <button className="btn-ghost logout-btn" onClick={handleLogout}>Sign out</button>
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
