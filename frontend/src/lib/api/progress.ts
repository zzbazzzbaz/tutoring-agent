import { api } from "./client";
import type { ProjectProgress } from "@/lib/types";

export interface SessionProgressResponse {
  session_id: string;
  progress: ProjectProgress;
  updated_at: string;
}

export const progressApi = {
  get: (sessionId: string) =>
    api.get<SessionProgressResponse>(`/progress/sessions/${sessionId}`),
};
