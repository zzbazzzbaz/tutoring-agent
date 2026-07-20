export interface SessionOut {
  id: string
  user_id: string
  mode: 'free' | 'project'
  project_id: string | null
  project_name: string | null
  title: string | null
  last_active_at: string
  created_at: string
}

export interface SessionCreate {
  mode: 'free' | 'project'
  project_id?: string
}
