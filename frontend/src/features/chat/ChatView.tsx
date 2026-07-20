import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import QuizCard from './QuizCard'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'

export default function ChatView() {
  const { t } = useTranslation()
  const currentSession = useChatStore(s => s.currentSession)
  const items = useChatStore(s => s.items)
  const streamStatus = useChatStore(s => s.streamStatus)
  const streamingContent = useChatStore(s => s.streamingContent)
  const pendingQuiz = useChatStore(s => s.pendingQuiz)
  const sendMessage = useChatStore(s => s.sendMessage)
  const submitQuiz = useChatStore(s => s.submitQuiz)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, streamingContent])

  const inputDisabled = streamStatus === 'streaming' || streamStatus === 'quiz_interrupted'
  const sessionEnded = currentSession?.status === 'ended'

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {items.map((item, idx) => {
          if (item.type === 'message') {
            return <MessageBubble key={idx} message={item.data} />
          } else if (item.type === 'quiz') {
            const q = item.data
            return (
              <QuizCard
                key={idx}
                quiz={q}
                status={q.status}
                userAnswer={q.user_answer}
                correctAnswer={q.answer}
                analysis={q.analysis}
                onSubmit={() => {}}
                onSkip={() => {}}
              />
            )
          }
          return null
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
      </div>
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled || sessionEnded}
        placeholder={sessionEnded ? t('chat.sessionEnded') : undefined}
      />
    </div>
  )
}
