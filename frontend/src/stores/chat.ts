import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import { createSelectors } from '@/lib/utils'
import type { SessionOut, HistoryResponse } from '@/types/session'
import type { QuestionOut, QuizInterruptData } from '@/types/question'
import type { ChatItem, StreamStatus } from '@/types/chat'

interface ChatState {
  sessions: SessionOut[]
  currentSession: SessionOut | null
  items: ChatItem[]
  streamStatus: StreamStatus
  pendingQuiz: QuizInterruptData | null
  streamingContent: string
  lastError: { message: string; code: string } | null
  currentAbort: AbortController | null
  loadingSession: boolean
  loadingSessions: boolean

  loadSessions: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  submitQuiz: (action: 'answer' | 'skip', answer?: string) => Promise<void>
  retryLastMessage: () => Promise<void>
  recoverFromHistory: () => Promise<void>
  resetStream: () => void
  clearCurrent: () => void
}

function makeAgentMsg(sessionId: string, content: string) {
  return {
    type: 'message' as const,
    data: {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'agent' as const,
      content,
      created_at: new Date().toISOString(),
    },
  }
}

function makeToolItem(sessionId: string, toolName: string, toolInput: Record<string, unknown>) {
  return {
    type: 'message' as const,
    data: {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'tool' as const,
      content: '',
      tool_name: toolName,
      tool_input: toolInput,
      created_at: new Date().toISOString(),
    },
  }
}

const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSession: null,
  items: [],
  streamStatus: 'idle',
  pendingQuiz: null,
  streamingContent: '',
  lastError: null,
  currentAbort: null,
  loadingSession: false,
  loadingSessions: false,

  loadSessions: async () => {
    set({ loadingSessions: true })
    try {
      const sessions = await sessionsApi.list({ limit: 50 })
      set({ sessions })
    } finally {
      set({ loadingSessions: false })
    }
  },

  selectSession: async id => {
    set({ loadingSession: true, streamStatus: 'idle', pendingQuiz: null, streamingContent: '', lastError: null })
    try {
      const [session, history] = await Promise.all([
        sessionsApi.get(id),
        sessionsApi.getHistory(id),
      ])
      set({
        currentSession: session,
        items: history.items,
        pendingQuiz: history.pending_quiz,
        streamStatus: history.pending_quiz ? 'quiz_interrupted' : (history.processing ? 'streaming' : 'idle'),
      })
    } finally {
      set({ loadingSession: false })
    }
  },

  sendMessage: async content => {
    const { currentSession } = get()
    if (!currentSession) return
    if (get().streamStatus === 'streaming' || get().streamStatus === 'quiz_interrupted') return

    const userMsg = {
      type: 'message' as const,
      data: {
        id: crypto.randomUUID(),
        session_id: currentSession.id,
        role: 'user' as const,
        content,
        created_at: new Date().toISOString(),
      },
    }
    set(state => ({
      items: [...state.items, userMsg],
      streamStatus: 'streaming' as const,
      streamingContent: '',
      lastError: null,
    }))

    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, content, ac.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(currentSession.id, ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentMsg(currentSession.id, get().streamingContent)], streamStatus: 'idle' as const, streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentMsg(currentSession.id, get().streamingContent)], streamingContent: '' }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'error', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断')
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        const is409 = e.message?.includes('409')
        if (is409) {
          toast.info('请先回答上方题目')
          await get().recoverFromHistory()
        } else {
          await new Promise(r => setTimeout(r, 2000))
          await get().recoverFromHistory()
        }
      }
    } finally {
      set({ currentAbort: null })
    }
  },

  submitQuiz: async (action, answer) => {
    const { currentSession, pendingQuiz, currentAbort } = get()
    if (!currentSession || !pendingQuiz) return

    set({ streamStatus: 'streaming', streamingContent: '' })

    try {
      for await (const ev of resumeQuiz(currentSession.id, action, answer ?? null, currentAbort?.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(currentSession.id, ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const question: QuestionOut = {
                ...pendingQuiz,
                id: pendingQuiz.question_id,
                session_id: currentSession.id,
                answer: '',
                analysis: null,
                status: action === 'skip' ? 'skipped' : 'answered',
                user_answer: action === 'skip' ? null : (answer ?? null),
                created_at: new Date().toISOString(),
                answered_at: new Date().toISOString(),
              }
              const qItem = { type: 'quiz' as const, data: question }
              const agentMsg = makeAgentMsg(currentSession.id, get().streamingContent)
              set(state => ({ items: [...state.items, qItem, agentMsg], pendingQuiz: null, streamStatus: 'idle' as const, streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentMsg(currentSession.id, get().streamingContent)], streamingContent: '' }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
          case 'error':
            set({ streamStatus: 'quiz_interrupted', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: '连接中断，请重新答题', code: 'STREAM_CLOSED' } })
        toast.error('连接中断，请重新答题')
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        await new Promise(r => setTimeout(r, 2000))
        await get().recoverFromHistory()
      }
    } finally {
      set({ currentAbort: null })
    }
  },

  retryLastMessage: async () => {
    const { currentSession, items } = get()
    if (!currentSession) return
    const lastUserMsg = [...items].reverse().find(i => i.type === 'message' && i.data.role === 'user')
    if (!lastUserMsg || lastUserMsg.type !== 'message') return

    set({ streamStatus: 'streaming', streamingContent: '', lastError: null })
    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, lastUserMsg.data.content, ac.signal, true)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(currentSession.id, ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentMsg(currentSession.id, get().streamingContent)], streamStatus: 'idle' as const, streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentMsg(currentSession.id, get().streamingContent)], streamingContent: '' }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        await new Promise(r => setTimeout(r, 2000))
        await get().recoverFromHistory()
      }
    } finally {
      set({ currentAbort: null })
    }
  },

  recoverFromHistory: async () => {
    const { currentSession } = get()
    if (!currentSession) return
    try {
      const history: HistoryResponse = await sessionsApi.getHistory(currentSession.id)
      if (history.pending_quiz) {
        set({ items: history.items, pendingQuiz: history.pending_quiz, streamStatus: 'quiz_interrupted', streamingContent: '' })
      } else if (history.processing) {
        set({ items: history.items, streamStatus: 'streaming' })
        setTimeout(() => get().recoverFromHistory(), 3000)
      } else {
        const lastAgent = [...history.items].reverse().find(i => i.type === 'message' && i.data.role === 'agent')
        if (lastAgent) {
          set({ items: history.items, streamStatus: 'idle', streamingContent: '' })
        } else {
          set({ items: history.items, streamStatus: 'error', lastError: { message: '连接中断，点击重试', code: 'RETRYABLE' }, streamingContent: '' })
        }
      }
    } catch {
      set({ streamStatus: 'error', lastError: { message: '网络错误', code: 'NETWORK' } })
    }
  },

  resetStream: () => {
    const ac = get().currentAbort
    if (ac) ac.abort()
    set({
      streamStatus: 'idle',
      streamingContent: '',
      pendingQuiz: null,
      lastError: null,
      currentAbort: null,
    })
  },

  clearCurrent: () => {
    get().resetStream()
    set({ currentSession: null, items: [], loadingSession: false })
  },
}))

export const useChat = createSelectors(useChatStore)
export { useChatStore }
