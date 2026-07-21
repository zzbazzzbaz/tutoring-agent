import { apiClient } from './client'
import type { SessionOut, SessionCreate, HistoryResponse } from '@/types/session'

export const sessionsApi = {
  list: async (params?: { status?: string; mode?: string; limit?: number; offset?: number }) => {
    const { data } = await apiClient.get<SessionOut[]>('/sessions', { params })
    return data
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<SessionOut>(`/sessions/${id}`)
    return data
  },
  create: async (body: SessionCreate) => {
    const { data } = await apiClient.post<SessionOut>('/sessions', body)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/sessions/${id}`)
  },
  getHistory: async (id: string) => {
    const { data } = await apiClient.get<HistoryResponse>(`/sessions/${id}/history`)
    return data
  },
}
