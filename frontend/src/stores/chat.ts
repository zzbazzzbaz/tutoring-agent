import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import { createSelectors } from '@/lib/utils'
import type { SessionOut } from '@/types/session'
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
  resetStream: () => void
  clearCurrent: () => void
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
      const [session, messages, questions] = await Promise.all([
        sessionsApi.get(id),
        sessionsApi.listMessages(id),
        sessionsApi.listQuestions(id),
      ])
      const items: ChatItem[] = [
        ...messages.map(m => ({ type: 'message' as const, data: m })),
        ...questions.map(q => ({ type: 'quiz' as const, data: q })),
      ].sort((a, b) => +new Date(a.data.created_at) - +new Date(b.data.created_at))
      set({ currentSession: session, items })
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
            set(state => ({
              streamingContent: state.streamingContent + ev.data.content,
            }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const agentMsg = {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(),
                  session_id: currentSession.id,
                  role: 'agent' as const,
                  content: get().streamingContent,
                  created_at: new Date().toISOString(),
                },
              }
              set(state => ({
                items: [...state.items, agentMsg],
                streamStatus: 'idle' as const,
                streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            set(state => ({ items: state.items.filter(it => it !== userMsg) }))
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'error', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断')
        set(state => ({ items: state.items.filter(it => it !== userMsg) }))
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ streamStatus: 'error', lastError: { message: String(e), code: 'NETWORK' } })
        toast.error('网络错误')
        set(state => ({ items: state.items.filter(it => it !== userMsg) }))
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
              const agentMsg = {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(),
                  session_id: currentSession.id,
                  role: 'agent' as const,
                  content: get().streamingContent,
                  created_at: new Date().toISOString(),
                },
              }
              set(state => ({
                items: [...state.items, qItem, agentMsg],
                pendingQuiz: null,
                streamStatus: 'idle' as const,
                streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'quiz_interrupted', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断，请重新答题')
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: String(e), code: 'NETWORK' } })
        toast.error('网络错误，请重新答题')
      }
    } finally {
      set({ currentAbort: null })
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
