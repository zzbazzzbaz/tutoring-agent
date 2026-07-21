import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import { createSelectors } from '@/lib/utils'
import type { SessionOut, HistoryResponse } from '@/types/session'
import type { HistoryItem, QuizInterruptData } from '@/types/message'
import type { StreamStatus } from '@/types/chat'

interface ChatState {
  sessions: SessionOut[]
  currentSession: SessionOut | null
  items: HistoryItem[]
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

function makeUserItem(content: string): HistoryItem {
  return { type: 'user', content }
}

function makeAgentItem(content: string): HistoryItem {
  return { type: 'agent', content }
}

function makeToolItem(toolName: string, toolInput: Record<string, unknown>): HistoryItem {
  return { type: 'tool_call', tool_name: toolName, tool_input: toolInput }
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

    set(state => ({
      items: [...state.items, makeUserItem(content)],
      streamStatus: 'streaming',
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
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
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
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const quizItem: HistoryItem = {
                type: 'quiz',
                quiz_id: pendingQuiz.question_id,
                topic: pendingQuiz.topic,
                q_type: pendingQuiz.q_type,
                stem: pendingQuiz.stem,
                options: pendingQuiz.options,
                status: action === 'skip' ? 'skipped' : 'answered',
                user_answer: action === 'skip' ? null : (answer ?? null),
              }
              const agentItem = makeAgentItem(get().streamingContent)
              set(state => ({ items: [...state.items, quizItem, agentItem], pendingQuiz: null, streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
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
    const lastUserMsg = [...items].reverse().find(e => e.type === 'user')
    if (!lastUserMsg?.content) return

    set({ streamStatus: 'streaming', streamingContent: '', lastError: null })
    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, lastUserMsg.content, ac.signal, true)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
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
        const lastAgent = [...history.items].reverse().find(e => e.type === 'agent')
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
