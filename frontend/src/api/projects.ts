import { apiClient } from './client'
import type { ProjectOut, ProjectCreate, ProjectUpdate } from '@/types/project'

export const projectsApi = {
  list: async (statusFilter?: string) => {
    const { data } = await apiClient.get<ProjectOut[]>('/projects', {
      params: statusFilter ? { status_filter: statusFilter } : undefined,
    })
    return data
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<ProjectOut>(`/projects/${id}`)
    return data
  },
  create: async (body: ProjectCreate) => {
    const { data } = await apiClient.post<ProjectOut>('/projects', body)
    return data
  },
  update: async (id: string, body: ProjectUpdate) => {
    const { data } = await apiClient.patch<ProjectOut>(`/projects/${id}`, body)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/projects/${id}`)
  },
}
