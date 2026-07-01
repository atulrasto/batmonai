import { api } from './client'
import type { TokenResponse, User } from '../types'

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password })
  return data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}

export async function me(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}
