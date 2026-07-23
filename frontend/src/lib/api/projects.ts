import { api } from "./client";
import type { Page, Project, ProjectCreate, ProjectUpdate } from "@/lib/types";

function buildListQuery(status?: string, page = 1, pageSize = 20) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) params.set("status", status);
  return params.toString();
}

export const projectsApi = {
  list: (status?: string, page = 1, pageSize = 20) =>
    api.get<Page<Project>>(`/projects?${buildListQuery(status, page, pageSize)}`),

  get: (id: string) => api.get<Project>(`/projects/${id}`),

  create: (data: ProjectCreate) => api.post<Project>("/projects", data),

  update: (id: string, data: ProjectUpdate) =>
    api.patch<Project>(`/projects/${id}`, data),

  delete: (id: string) => api.delete<void>(`/projects/${id}`),
};
