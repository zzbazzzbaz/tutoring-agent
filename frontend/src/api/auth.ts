import { apiClient } from './client'
import type { LoginResponse } from '@/types/user'

export const authApi = {
  login: async (username: string, password: string) => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', {
      username,
      password,
    })
    return data
  },
  logout: async () => {
    await apiClient.post('/auth/logout')
  },
  me: async () => {
    const { data } = await apiClient.get('/auth/me')
    return data
  },
  changePassword: async (oldPassword: string, newPassword: string) => {
    await apiClient.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}
