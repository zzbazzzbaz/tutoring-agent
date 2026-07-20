export interface QuestionOut {
  id: string
  session_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
  answer: string
  analysis: string | null
  status: 'pending' | 'answered' | 'skipped'
  user_answer: string | null
  created_at: string
  answered_at: string | null
}

export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
