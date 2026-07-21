import type { ChatEvent } from './message'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type ChatItem = ChatEvent
