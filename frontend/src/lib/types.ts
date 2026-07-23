export type UserRole = "student" | "teacher";

export interface User {
  id: string;
  username: string;
  role: UserRole;
  name: string;
  avatar_url?: string | null;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export type SessionMode = "free" | "project";

export interface Session {
  id: string;
  user_id: string;
  mode: SessionMode;
  project_id: string | null;
  project_name: string | null;
  title: string | null;
  last_active_at: string;
  created_at: string;
}

export interface SessionCreate {
  mode: SessionMode;
  project_id?: string;
}

export type ProjectStatus = "draft" | "published";

export interface Project {
  id: string;
  name: string;
  background_md: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  background_md: string;
  status: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  background_md?: string;
  status?: ProjectStatus;
}

export interface Student {
  id: string;
  username: string;
  role: string;
  name: string;
  avatar_url?: string | null;
  created_at: string;
}

export interface ImportResult {
  total: number;
  created: number;
  skipped: number;
  errors: string[];
}
