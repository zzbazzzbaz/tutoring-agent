import { apiClient } from './client'
import type { UserOut } from '@/types/user'
import type { SessionOut } from '@/types/session'

export interface ImportResult {
  total: number
  created: number
  skipped: number
  errors: string[]
}

export const usersApi = {
  listStudents: async () => {
    const { data } = await apiClient.get<UserOut[]>('/users/students')
    return data
  },
  listTeachers: async () => {
    const { data } = await apiClient.get<UserOut[]>('/users/teachers')
    return data
  },
  deleteUser: async (id: string) => {
    await apiClient.delete(`/users/${id}`)
  },
  resetPassword: async (id: string) => {
    const { data } = await apiClient.post<{ message: string }>(`/users/${id}/reset-password`)
    return data
  },
  importStudents: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post<ImportResult>('/users/students/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  downloadTemplate: async () => {
    const response = await apiClient.get('/users/students/template', { responseType: 'blob' })
    const url = window.URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'students_template.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  },
  listUserSessions: async (userId: string) => {
    const { data } = await apiClient.get<SessionOut[]>(`/users/${userId}/sessions`, {
      params: { limit: 50 },
    })
    return data
  },
}
