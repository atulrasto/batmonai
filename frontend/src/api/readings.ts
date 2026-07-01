import { api } from './client'
import type { DcPoint, AcPoint, SensorPoint } from '../types'

export const dcLatest = (batteryId: string) =>
  api.get<DcPoint>(`/readings/dc/${batteryId}/latest`).then(r => r.data)

export const dcRange = (batteryId: string, from?: string, to?: string) =>
  api.get<DcPoint[]>(`/readings/dc/${batteryId}`, { params: { from, to } }).then(r => r.data)

export const acLatest = (channelId: string) =>
  api.get<AcPoint>(`/readings/ac/${channelId}/latest`).then(r => r.data)

export const acRange = (channelId: string, from?: string, to?: string) =>
  api.get<AcPoint[]>(`/readings/ac/${channelId}`, { params: { from, to } }).then(r => r.data)

export const sensorLatest = (sensorId: string) =>
  api.get<SensorPoint>(`/readings/sensor/${sensorId}/latest`).then(r => r.data)

export const sensorRange = (sensorId: string, from?: string, to?: string) =>
  api.get<SensorPoint[]>(`/readings/sensor/${sensorId}`, { params: { from, to } }).then(r => r.data)
