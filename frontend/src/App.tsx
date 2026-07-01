import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ChangePasswordPage from './pages/ChangePasswordPage'
import DashboardPage from './pages/DashboardPage'
import ClientsPage from './pages/admin/ClientsPage'
import FlashDevicePage from './pages/admin/FlashDevicePage'
import SitesPage from './pages/SitesPage'
import AppliancePage from './pages/AppliancePage'
import ProvisionDevicePage from './pages/ProvisionDevicePage'
import ReportsPage from './pages/ReportsPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/admin/clients" element={<ClientsPage />} />
            <Route path="/admin/flash-device" element={<FlashDevicePage />} />
            <Route path="/sites" element={<SitesPage />} />
            <Route path="/appliances/:applianceId" element={<AppliancePage />} />
            <Route path="/provision-device" element={<ProvisionDevicePage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
