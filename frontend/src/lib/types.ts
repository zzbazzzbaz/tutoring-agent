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

export interface SessionUpdate {
  title?: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
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

export type LightRAGDocumentStatus =
  | "pending"
  | "parsing"
  | "analyzing"
  | "processing"
  | "preprocessed"
  | "processed"
  | "failed";

export interface LightRAGDocument {
  id: string;
  content_summary?: string | null;
  content_length?: number | null;
  status: LightRAGDocumentStatus;
  created_at?: string | null;
  updated_at?: string | null;
  track_id?: string | null;
  chunks_count?: number | null;
  error_msg?: string | null;
  metadata?: Record<string, unknown>;
  file_path?: string | null;
}

export interface LightRAGDocumentsResponse {
  items: LightRAGDocument[];
  total: number;
  page: number;
  page_size: number;
}

export interface LightRAGPipelineStatus {
  busy: boolean;
  job_name?: string | null;
  docs?: number;
  cur_batch?: number;
  batchs?: number;
  request_pending?: boolean;
  latest_message?: string;
  history_messages?: string[] | null;
}

export interface LightRAGGraphNode {
  id: string;
  labels?: string[];
  properties?: Record<string, unknown>;
}

export interface LightRAGGraphEdge {
  id?: string;
  source: string;
  target: string;
  type?: string;
  properties?: Record<string, unknown>;
}

export interface LightRAGGraphResponse {
  nodes: LightRAGGraphNode[];
  edges: LightRAGGraphEdge[];
}
