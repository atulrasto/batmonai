import { api } from './client'
import type { Client, Site, Appliance, Battery, AcChannel, Rs485Sensor, AppEvent } from '../types'

// ── Clients ────────────────────────────────────────────────────────────────────
export const listClients = () => api.get<Client[]>('/clients/').then(r => r.data)
export const createClient = (name: string, primary_email: string) =>
  api.post<Client>('/clients/', { name, primary_email }).then(r => r.data)
export const updateClient = (id: string, payload: { name?: string; webhook_url?: string | null; is_active?: boolean }) =>
  api.patch<Client>(`/clients/${id}`, payload).then(r => r.data)

// ── Sites ──────────────────────────────────────────────────────────────────────
export const listSites = () => api.get<Site[]>('/sites/').then(r => r.data)
export const createSite = (name: string, client_id?: string, location?: string) =>
  api.post<Site>('/sites/', { name, client_id, location }).then(r => r.data)
export const deleteSite = (id: string) => api.delete(`/sites/${id}`)

// ── Appliances ─────────────────────────────────────────────────────────────────
export const listAppliances = () => api.get<Appliance[]>('/appliances/').then(r => r.data)
export const getAppliance = (id: string) => api.get<Appliance>(`/appliances/${id}`).then(r => r.data)
export const createAppliance = (payload: {
  site_id: string; name: string; device_secret: string; client_id?: string
}) => api.post<Appliance>('/appliances/', payload).then(r => r.data)

// ── Batteries ─────────────────────────────────────────────────────────────────
export const listBatteries = () => api.get<Battery[]>('/batteries/').then(r => r.data)
export const createBattery = (payload: {
  appliance_id: string; name?: string; modbus_addr: number
  shunt_rating_a?: number; nominal_v?: number; client_id?: string
}) => api.post<Battery>('/batteries/', payload).then(r => r.data)

// ── AC Channels ────────────────────────────────────────────────────────────────
export const listAcChannels = () => api.get<AcChannel[]>('/ac-channels/').then(r => r.data)
export const createAcChannel = (payload: {
  appliance_id: string; name: string; modbus_addr: number; role: string; client_id?: string
}) => api.post<AcChannel>('/ac-channels/', payload).then(r => r.data)

// ── RS485 Sensors ──────────────────────────────────────────────────────────────
export const listSensors = () => api.get<Rs485Sensor[]>('/sensors/').then(r => r.data)
export const createSensor = (payload: {
  appliance_id: string; sensor_type: string; modbus_addr: number
  name: string; config?: Record<string, unknown>; client_id?: string
}) => api.post<Rs485Sensor>('/sensors/', payload).then(r => r.data)

// ── Device secret ─────────────────────────────────────────────────────────────
export const regenerateSecret = (applianceId: string) =>
  api.post<{ device_secret: string; appliance_uid: string; appliance_id: string }>(
    `/appliances/${applianceId}/regenerate-secret`
  ).then(r => r.data)

// ── Patch / rename ─────────────────────────────────────────────────────────────
export const updateAppliance = (id: string, payload: { name?: string; is_active?: boolean }) =>
  api.patch<Appliance>(`/appliances/${id}`, payload).then(r => r.data)

export const updateBattery = (id: string, payload: { name?: string }) =>
  api.patch<Battery>(`/batteries/${id}`, payload).then(r => r.data)

export const updateAcChannel = (id: string, payload: { name?: string; role?: string }) =>
  api.patch<AcChannel>(`/ac-channels/${id}`, payload).then(r => r.data)

export const updateSensor = (id: string, payload: { name?: string }) =>
  api.patch<Rs485Sensor>(`/sensors/${id}`, payload).then(r => r.data)

// ── Events ─────────────────────────────────────────────────────────────────────
export const listEvents = (params?: { appliance_id?: string; open_only?: boolean; limit?: number }) =>
  api.get<AppEvent[]>('/events/', { params }).then(r => r.data)

export const getEventCounts = () =>
  api.get<Record<string, { warning: number; critical: number; info: number; total: number }>>(
    '/events/counts'
  ).then(r => r.data)
