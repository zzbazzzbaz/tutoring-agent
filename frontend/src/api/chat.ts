import { getAuthToken } from './client'
import { parseSSE, type SSEEvent } from '@/lib/parseSSE'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function* streamMessage(
  sessionId: string,
  content: string,
  signal?: AbortSignal,
  retry: boolean = false,
): AsyncGenerator<SSEEvent> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content, retry }),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  yield* parseSSE(res)
}

export async function* resumeQuiz(
  sessionId: string,
  action: 'answer' | 'skip',
  answer: string | null,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = getAuthToken()
  const body: Record<string, unknown> = { action }
  if (action === 'answer' && answer !== null) {
    body.answer = answer
  }
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/quiz/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  yield* parseSSE(res)
}
