export interface ToolEventData {
  tool_name: string
  tool_input: Record<string, unknown> | null
  tool_output: string | null
}

export interface QuizEventData {
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
  answer: string
  analysis: string | null
  user_answer: string | null
}

export interface ChatEvent {
  id: string
  session_id: string
  type: 'user' | 'agent' | 'tool' | 'quiz'
  created_at: string
  content: string | null
  data: ToolEventData | QuizEventData | null
  status: 'pending' | 'answered' | 'skipped' | null
  answered_at: string | null
}

export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
