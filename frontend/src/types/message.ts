export interface MessageOut {
  id: string
  session_id: string
  role: 'user' | 'agent'
  content: string
  created_at: string
}
