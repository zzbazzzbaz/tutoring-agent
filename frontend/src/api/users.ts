import { apiClient } from './client'
import type { UserOut } from '@/types/user'

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
}
