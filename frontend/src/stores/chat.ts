import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import type { SessionOut } from '@/types/session'
import type { QuestionOut, QuizInterruptData } from '@/types/question'
import type { ChatItem, StreamStatus } from '@/types/chat'
interface ChatState {
  currentSession: SessionOut | null
  items: ChatItem[]
  streamStatus: StreamStatus
  pendingQuiz: QuizInterruptData | null
  streamingAgentContent: string
  lastError: { message: string; code: string } | null
  currentAbort: AbortController | null
  loadingSession: boolean

  loadSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  submitQuiz: (action: 'answer' | 'skip', answer?: string) => Promise<void>
  resetStream: () => void
  clearCurrent: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  currentSession: null,
  items: [],
  streamStatus: 'idle',
  pendingQuiz: null,
  streamingAgentContent: '',
  lastError: null,
  currentAbort: null,
  loadingSession: false,

  loadSession: async id => {
    set({ loadingSession: true })
    try {
      const [session, messages, questions] = await Promise.all([
        sessionsApi.get(id),
        sessionsApi.listMessages(id),
        sessionsApi.listQuestions(id),
      ])
      const items: ChatItem[] = [
        ...messages.map(m => ({ type: 'message' as const, ...m })),
        ...questions.map(q => ({ type: 'question' as const, question: q })),
      ].sort((a, b) => {
        const aTime = a.type === 'message' ? a.created_at : a.question.created_at
        const bTime = b.type === 'message' ? b.created_at : b.question.created_at
        return +new Date(aTime) - +new Date(bTime)
      })

      set({
        currentSession: session,
        items,
        streamStatus: 'idle',
        pendingQuiz: null,
        streamingAgentContent: '',
        lastError: null,
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
      role: 'user' as const,
      content,
      created_at: new Date().toISOString(),
    }
    set(state => ({
      items: [...state.items, userMsg],
      streamStatus: 'streaming' as const,
      streamingAgentContent: '',
      lastError: null,
    }))

    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, content, ac.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({
              streamingAgentContent: state.streamingAgentContent + ev.data.content,
            }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const agentMsg = {
                type: 'message' as const,
                role: 'agent' as const,
                content: get().streamingAgentContent,
                created_at: new Date().toISOString(),
              }
              set(state => ({
                items: [...state.items, agentMsg],
                streamStatus: 'idle' as const,
                streamingAgentContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingAgentContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            set(state => ({ items: state.items.filter(it => it !== userMsg) }))
            break
        }
      }
      // 检测流意外断开
      if (get().streamStatus === 'streaming') {
        set({
          streamStatus: 'error',
          lastError: { message: '连接中断', code: 'STREAM_CLOSED' },
        })
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

    set({ streamStatus: 'streaming', streamingAgentContent: '' })

    try {
      for await (const ev of resumeQuiz(
        currentSession.id,
        action,
        answer ?? null,
        currentAbort?.signal,
      )) {
        switch (ev.event) {
          case 'text':
            set(state => ({
              streamingAgentContent: state.streamingAgentContent + ev.data.content,
            }))
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
                verdict: null,
                diagnosis: null,
                created_at: new Date().toISOString(),
                answered_at: new Date().toISOString(),
              }
              const qItem = {
                type: 'question' as const,
                question,
              }
              const agentMsg = {
                type: 'message' as const,
                role: 'agent' as const,
                content: get().streamingAgentContent,
                created_at: new Date().toISOString(),
              }
              set(state => ({
                items: [...state.items, qItem, agentMsg],
                pendingQuiz: null,
                streamStatus: 'idle' as const,
                streamingAgentContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingAgentContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'quiz_interrupted', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      // 检测流意外断开
      if (get().streamStatus === 'streaming') {
        set({
          streamStatus: 'quiz_interrupted',
          lastError: { message: '连接中断', code: 'STREAM_CLOSED' },
        })
        toast.error('连接中断，请重新答题')
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({
          streamStatus: 'quiz_interrupted',
          lastError: { message: String(e), code: 'NETWORK' },
        })
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
      streamingAgentContent: '',
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
