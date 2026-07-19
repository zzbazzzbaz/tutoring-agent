import { apiClient } from './client'
import type { ProjectOut, ProjectCreate, ProjectUpdate } from '@/types/project'

export const projectsApi = {
  list: async (statusFilter?: 'draft' | 'published'): Promise<ProjectOut[]> => {
    const res = await apiClient.get<ProjectOut[]>('/projects', {
      params: statusFilter ? { status_filter: statusFilter } : {},
    })
    return res.data
  },

  get: async (id: string): Promise<ProjectOut> => {
    const res = await apiClient.get<ProjectOut>(`/projects/${id}`)
    return res.data
  },

  create: async (body: ProjectCreate): Promise<ProjectOut> => {
    const res = await apiClient.post<ProjectOut>('/projects', body)
    return res.data
  },

  update: async (id: string, body: ProjectUpdate): Promise<ProjectOut> => {
    const res = await apiClient.patch<ProjectOut>(`/projects/${id}`, body)
    return res.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/projects/${id}`)
  },
}
