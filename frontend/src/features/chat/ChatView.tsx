import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import QuizCard from './QuizCard'
import ToolCallBubble from './ToolCallBubble'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { HistoryItem } from '@/types/message'

export default function ChatView() {
  const items = useChatStore(s => s.items)
  const streamStatus = useChatStore(s => s.streamStatus)
  const streamingContent = useChatStore(s => s.streamingContent)
  const pendingQuiz = useChatStore(s => s.pendingQuiz)
  const lastError = useChatStore(s => s.lastError)
  const sendMessage = useChatStore(s => s.sendMessage)
  const submitQuiz = useChatStore(s => s.submitQuiz)
  const retryLastMessage = useChatStore(s => s.retryLastMessage)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, streamingContent, pendingQuiz])

  const inputDisabled = streamStatus === 'streaming' || streamStatus === 'quiz_interrupted'
  const showRetry = streamStatus === 'error' && lastError?.code === 'RETRYABLE'

  const pendingQuizItem: HistoryItem | null = pendingQuiz ? {
    type: 'quiz',
    quiz_id: pendingQuiz.question_id,
    topic: pendingQuiz.topic,
    q_type: pendingQuiz.q_type,
    stem: pendingQuiz.stem,
    options: pendingQuiz.options,
    status: 'pending',
    user_answer: null,
  } : null

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {items.map((item, idx) => {
          switch (item.type) {
            case 'user':
            case 'agent':
              return <MessageBubble key={idx} message={item} />
            case 'tool_call':
              return <ToolCallBubble key={idx} message={item} />
            case 'quiz':
              if (item.status === 'pending') return null
              return (
                <QuizCard
                  key={idx}
                  quiz={item}
                  status={item.status as 'pending' | 'answered' | 'skipped'}
                  userAnswer={item.user_answer}
                  onSubmit={() => {}}
                  onSkip={() => {}}
                />
              )
          }
        })}
        {streamStatus === 'streaming' && streamingContent && (
          <div className="flex gap-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
              <span className="text-xs">AI</span>
            </div>
            <div className="flex-1 text-sm">
              <MarkdownRenderer content={streamingContent} />
            </div>
          </div>
        )}
        {streamStatus === 'quiz_interrupted' && pendingQuizItem && (
          <QuizCard
            quiz={pendingQuizItem}
            status="pending"
            onSubmit={answer => submitQuiz('answer', answer)}
            onSkip={() => submitQuiz('skip')}
          />
        )}
        {showRetry && (
          <div className="flex justify-center">
            <button
              onClick={() => retryLastMessage()}
              className="rounded-lg border bg-muted/50 px-4 py-2 text-sm hover:bg-muted"
            >
              重试
            </button>
          </div>
        )}
      </div>
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled}
        hint={streamStatus === 'quiz_interrupted' ? '请先回答上方题目' : undefined}
      />
    </div>
  )
}
