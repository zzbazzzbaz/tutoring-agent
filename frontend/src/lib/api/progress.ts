import { api } from "./client";
import type { ProjectProgress } from "@/lib/types";

export interface ProjectProgressResponse {
  user_id: string;
  project_id: string;
  progress: ProjectProgress;
  updated_at: string;
}

export const progressApi = {
  get: (projectId: string, userId: string) =>
    api.get<ProjectProgressResponse>(
      `/progress/projects/${projectId}/users/${userId}`,
    ),
};
