import axios from 'axios'

// In dev: VITE_API_URL points directly to the API (e.g. http://localhost:8010)
// In Docker: VITE_API_URL is absent; calls use /api which nginx proxies to api:8000
const BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: BASE,
  timeout: 10_000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Only auto-logout on 401 when NOT on the login/change-password pages —
    // a failed login attempt itself returns 401 and must not trigger a redirect loop.
    if (err.response?.status === 401) {
      const onAuthPage = window.location.pathname === '/login' ||
        window.location.pathname === '/change-password'
      if (!onAuthPage) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)
