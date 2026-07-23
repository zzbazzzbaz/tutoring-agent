import { api } from "./client";
import type { Project, ProjectCreate, ProjectUpdate } from "@/lib/types";

export const projectsApi = {
  list: (status?: string) =>
    api.get<Project[]>(`/projects${status ? `?status=${status}` : ""}`),

  get: (id: string) => api.get<Project>(`/projects/${id}`),

  create: (data: ProjectCreate) => api.post<Project>("/projects", data),

  update: (id: string, data: ProjectUpdate) =>
    api.patch<Project>(`/projects/${id}`, data),

  delete: (id: string) => api.delete<void>(`/projects/${id}`),
};
