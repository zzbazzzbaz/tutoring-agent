import { apiClient } from './client'
import type { SessionOut, SessionCreate } from '@/types/session'
import type { MessageOut } from '@/types/message'
import type { QuestionOut } from '@/types/question'

export const sessionsApi = {
  list: async (params?: {
    status?: string
    mode?: 'free' | 'project'
    limit?: number
    offset?: number
  }): Promise<SessionOut[]> => {
    const res = await apiClient.get<SessionOut[]>('/sessions', { params })
    return res.data
  },

  get: async (id: string): Promise<SessionOut> => {
    const res = await apiClient.get<SessionOut>(`/sessions/${id}`)
    return res.data
  },

  create: async (body: SessionCreate): Promise<SessionOut> => {
    const res = await apiClient.post<SessionOut>('/sessions', body)
    return res.data
  },

  end: async (id: string): Promise<void> => {
    await apiClient.delete(`/sessions/${id}`)
  },

  listMessages: async (id: string, params?: { limit?: number; offset?: number }): Promise<MessageOut[]> => {
    const res = await apiClient.get<MessageOut[]>(`/sessions/${id}/messages`, { params })
    return res.data
  },

  listQuestions: async (id: string, status?: string): Promise<QuestionOut[]> => {
    const res = await apiClient.get<QuestionOut[]>(`/sessions/${id}/questions`, {
      params: status ? { status } : {},
    })
    return res.data
  },
}
