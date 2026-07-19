import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useChatStore } from '@/stores/chat'
import SessionHeader from './SessionHeader'
import MessageBubble from './MessageBubble'
import QuizCard from './QuizCard'
import ChatInput from './ChatInput'
import { ScrollArea } from '@/components/ui/scroll-area'

export default function SessionDetail() {
  const { id } = useParams<{ id: string }>()
  const currentSession = useChatStore(s => s.currentSession)
  const items = useChatStore(s => s.items)
  const loadingSession = useChatStore(s => s.loadingSession)
  const loadSession = useChatStore(s => s.loadSession)
  const streamStatus = useChatStore(s => s.streamStatus)
  const streamingAgentContent = useChatStore(s => s.streamingAgentContent)

  useEffect(() => {
    if (id) loadSession(id)
  }, [id, loadSession])

  if (loadingSession && !currentSession) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        加载中...
      </div>
    )
  }
  if (!currentSession) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        会话不存在
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <SessionHeader />
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          {items.map((item, idx) => {
            if (item.type === 'message') {
              return (
                <MessageBubble
                  key={`m-${idx}`}
                  role={item.role}
                  content={item.content}
                  createdAt={item.created_at}
                />
              )
            }
            return <QuizCard key={`q-${idx}`} question={item.question} locked />
          })}
          {streamStatus === 'streaming' && streamingAgentContent && (
            <MessageBubble
              role="agent"
              content={streamingAgentContent}
              createdAt={new Date().toISOString()}
              streaming
            />
          )}
        </div>
      </ScrollArea>
      <div className="border-t p-4">
        <ChatInput />
      </div>
    </div>
  )
}
