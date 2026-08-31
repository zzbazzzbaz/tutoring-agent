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

export interface MainlineDeliverable {
  title: string;
  instructions: string;
}

export interface MainlineStage {
  id: string;
  order: number;
  title: string;
  guide?: string;
  deliverable: MainlineDeliverable | null;
}

export interface Mainline {
  objective: string;
  stages: MainlineStage[];
}

export type StageStatus = "pending" | "in_progress" | "completed";

export interface StageProgress {
  status: StageStatus;
  deliverable: string | null;
  deliverable_done: boolean;
}

export type ProjectProgress = Record<string, StageProgress>;

export interface Project {
  id: string;
  name: string;
  background_md: string;
  mainline: Mainline | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  background_md: string;
  mainline?: Mainline | null;
  status: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  background_md?: string;
  mainline?: Mainline | null;
  status?: ProjectStatus;
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
// === 班级管理Class ===

export type ClassStatus = "active" | "archived";

export interface ClassInfo {
  id: string;
  grade: string;
  classname: string;
  teacher_id: string;
  status: ClassStatus;
  created_at: string;
  updated_at: string;
  student_count: number;
  teacher_name: string | null;
}

export interface ClassCreate {
  grade: string;
  classname: string;
}

export interface ClassUpdate {
  grade?: string;
  classname?: string;
  status?: ClassStatus;
}

export interface ClassStudent {
  user_id: string;
  username: string;
  name: string;
  joined_at: string;
}

export interface ClassSession {
  id: string;
  user_id: string;
  user_name: string | null;
  username: string | null;
  title: string | null;
  mode: string;
  project_id: string | null;
  project_name: string | null;
  last_active_at: string;
  created_at: string;
}

export interface ClassStats {
  total_students: number;
  total_sessions: number;
  active_today: number;
}

export interface AddStudentsRequest {
  user_ids: string[];
}

export interface Student {
  id: string;
  username: string;
  role: string;
  name: string;
  avatar_url?: string | null;
  created_at: string;
}

// === 统计分析-->学情总览 Analytics ===

export interface DashboardOverview {
  total_students: number;
  active_today: number;
  total_sessions: number;
  weekly_avg_sessions: number;
  pending_alert_count: number;
}

export type AlertType = "inactive";

export interface AnomalyStudent {
  user_id: string;
  name: string;
  username: string;
  last_active_at: string | null;
  inactive_days: number;
  alert_type: AlertType;
  class_id: string;
  class_name: string;
}

export interface LearningTrendPoint {
  date: string;
  session_count: number;
  active_student_count: number;
}

export interface ClassComparison {
  class_id: string;
  class_name: string;
  total_students: number;
  active_today: number;
  active_rate: number;
}

export interface ModeCount {
  mode: "free" | "project";
  count: number;
}

export interface StudentRanking {
  user_id: string;
  name: string;
  username: string;
  total_sessions: number;
  active_days: number;
  last_active_at: string | null;
}

export interface MessageStats {
  total_messages: number;
  student_messages: number;
  assistant_messages: number;
  avg_turns: number;
  knowledge_hit_rate: number;
}

export interface DashboardResponse {
  overview: DashboardOverview;
  anomalies: AnomalyStudent[];
  trend: LearningTrendPoint[];
  class_comparison: ClassComparison[];
  mode_distribution: ModeCount[];
  student_ranking: StudentRanking[];
  message_stats: MessageStats;
}

// ===统计分析--> 学生分析 Student Analysis ===

export interface StudentClassInfo {
  class_id: string;
  class_name: string;
  joined_at: string;
}

export interface StudentOverview {
  user_id: string;
  name: string;
  username: string;
  total_sessions: number;
  active_days: number;
  last_active_at: string | null;
  inactive_days: number;
  weekly_sessions: number;
  classes: StudentClassInfo[];
}

export interface StudentDailyActivity {
  date: string;
  session_count: number;
}

export interface StudentAnalysisResponse {
  overview: StudentOverview;
  daily_activity: StudentDailyActivity[];
}