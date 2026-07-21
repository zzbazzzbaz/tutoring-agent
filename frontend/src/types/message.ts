export interface MessageOut {
  id: string
  session_id: string
  role: 'user' | 'agent' | 'tool'
  content: string
  tool_name?: string | null
  tool_input?: Record<string, unknown> | null
  tool_output?: string | null
  created_at: string
}
