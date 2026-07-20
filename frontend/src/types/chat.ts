import type { MessageOut } from './message'
import type { QuestionOut } from './question'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type ChatItem =
  | { type: 'message'; data: MessageOut }
  | { type: 'quiz'; data: QuestionOut }
  | { type: 'streaming'; data: { content: string } }
