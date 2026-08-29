import { api } from "./client";
import type { Session, SessionCreate, SessionUpdate, Page } from "@/lib/types";

export const sessionsApi = {
  list: () => api.get<Session[]>("/sessions"),

  create: (data: SessionCreate) => api.post<Session>("/sessions", data),

  get: (id: string) => api.get<Session>(`/sessions/${id}`),

  update: (id: string, data: SessionUpdate) =>
    api.patch<Session>(`/sessions/${id}`, data),

  delete: (id: string) => api.delete<void>(`/sessions/${id}`),

  listByUser: (userId: string, page = 1, pageSize = 10) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return api.get<Page<Session>>(`/users/${userId}/sessions?${params.toString()}`);
  },
};
