export interface HistoryItem {
  type: 'user' | 'agent' | 'tool_call' | 'quiz'
  content?: string | null
  tool_name?: string | null
  tool_input?: Record<string, unknown> | null
  quiz_id?: string | null
  topic?: string | null
  q_type?: 'single' | 'multi' | 'short' | null
  stem?: string | null
  options?: string[] | null
  status?: 'pending' | 'answered' | 'skipped' | null
  user_answer?: string | null
}

export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
