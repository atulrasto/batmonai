export interface User {
  id: string
  email: string
  role: 'superuser' | 'client'
  client_id: string | null
  must_change_password: boolean
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  must_change_password: boolean
}

export interface Client {
  id: string
  name: string
  primary_email: string
  webhook_url: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Site {
  id: string
  client_id: string
  name: string
  slug: string
  location: string | null
  created_at: string
  updated_at: string
}

export interface Appliance {
  id: string
  client_id: string
  site_id: string
  appliance_uid: string
  name: string
  fw_version: string | null
  last_seen_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Battery {
  id: string
  client_id: string
  appliance_id: string
  battery_uid: string
  name: string
  modbus_addr: number
  shunt_rating_a: number
  capacity_ah: string | null
  chemistry: string
  nominal_v: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AcChannel {
  id: string
  client_id: string
  appliance_id: string
  channel_uid: string
  name: string
  modbus_addr: number
  role: 'inverter_input' | 'inverter_output' | 'load'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DcPoint {
  t: string
  v_avg: number
  v_min?: number
  v_max?: number
  i_avg: number
  i_min?: number
  i_max?: number
  p_avg: number
  energy_wh?: number
  alarm: number
  resolution: 'raw' | 'hourly' | 'daily'
}

export interface AcPoint {
  t: string
  v_avg: number
  v_min?: number
  v_max?: number
  i_avg: number
  p_avg: number
  freq_avg: number
  pf_avg: number
  energy_delta_wh?: number
  resolution: 'raw' | 'hourly' | 'daily'
}

export interface Rs485Sensor {
  id: string
  client_id: string
  appliance_id: string
  sensor_uid: string
  sensor_type: 'temp_humidity' | 'gas_h2' | string
  modbus_addr: number
  name: string
  config: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SensorPoint {
  t: string
  sensor_id: string
  sensor_type: string
  payload: Record<string, unknown>
}

export interface AppEvent {
  id: string
  client_id: string
  appliance_id: string
  kind: string
  severity: 'info' | 'warning' | 'critical'
  detail: Record<string, unknown> | null
  started_at: string
  resolved_at: string | null
  created_at: string
}
