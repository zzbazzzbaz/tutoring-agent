export interface ProjectOut {
  id: string
  name: string
  background_md: string
  status: 'draft' | 'published'
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  background_md: string
  status?: 'draft' | 'published'
}

export interface ProjectUpdate {
  name?: string
  background_md?: string
  status?: 'draft' | 'published'
}
