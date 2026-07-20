import { apiClient } from './client'
import type { SessionOut, SessionCreate } from '@/types/session'
import type { MessageOut } from '@/types/message'
import type { QuestionOut } from '@/types/question'

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
  listMessages: async (id: string, params?: { limit?: number; offset?: number }) => {
    const { data } = await apiClient.get<MessageOut[]>(`/sessions/${id}/messages`, { params })
    return data
  },
  listQuestions: async (id: string, params?: { status?: string }) => {
    const { data } = await apiClient.get<QuestionOut[]>(`/sessions/${id}/questions`, { params })
    return data
  },
}
