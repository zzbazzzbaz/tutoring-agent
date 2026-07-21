import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import QuizCard from './QuizCard'
import ToolCallBubble from './ToolCallBubble'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { QuizEventData } from '@/types/message'

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

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {items.map((event) => {
          switch (event.type) {
            case 'user':
            case 'agent':
              return <MessageBubble key={event.id} message={event} />
            case 'tool':
              return <ToolCallBubble key={event.id} message={event} />
            case 'quiz':
              return (
                <QuizCard
                  key={event.id}
                  quiz={event}
                  status={event.status as 'pending' | 'answered' | 'skipped'}
                  userAnswer={(event.data as QuizEventData)?.user_answer}
                  correctAnswer={(event.data as QuizEventData)?.answer}
                  analysis={(event.data as QuizEventData)?.analysis}
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
        {streamStatus === 'quiz_interrupted' && pendingQuiz && (
          <QuizCard
            quiz={pendingQuiz}
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
