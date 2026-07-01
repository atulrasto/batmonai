import { api } from './client'

export const startSim = (appliance_id: string, interval_s = 5) =>
  api.post('/dev/simulator/start', { appliance_id, interval_s }).then(r => r.data)

export const stopSim = (appliance_id: string) =>
  api.post('/dev/simulator/stop', { appliance_id }).then(r => r.data)

export const simStatus = () =>
  api.get<{ active: string[] }>('/dev/simulator/status').then(r => r.data)
