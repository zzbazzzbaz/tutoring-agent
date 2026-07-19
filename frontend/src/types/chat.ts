import type { QuestionOut } from './question'

export type ChatItem = MessageItem | QuestionItem

export interface MessageItem {
  type: 'message'
  id?: string
  role: 'user' | 'agent'
  content: string
  created_at: string
}

export interface QuestionItem {
  type: 'question'
  question: QuestionOut
}

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'
