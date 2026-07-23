import { api } from "./client";
import type { Session, SessionCreate } from "@/lib/types";

export const sessionsApi = {
  list: () => api.get<Session[]>("/sessions"),

  create: (data: SessionCreate) => api.post<Session>("/sessions", data),

  get: (id: string) => api.get<Session>(`/sessions/${id}`),

  delete: (id: string) => api.delete<void>(`/sessions/${id}`),

  listByUser: (userId: string) =>
    api.get<Session[]>(`/users/${userId}/sessions`),
};
