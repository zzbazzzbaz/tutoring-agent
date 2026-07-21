import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, MessageSquare, MessagesSquare, MessageSquarePlus } from 'lucide-react'
import { usersApi } from '@/api/users'
import { sessionsApi } from '@/api/sessions'
import { formatRelativeTime } from '@/lib/formatDate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import EmptyState from '@/features/shared/EmptyState'
import MessageBubble from '@/features/chat/MessageBubble'
import QuizCard from '@/features/chat/QuizCard'
import ToolCallBubble from '@/features/chat/ToolCallBubble'
import type { SessionOut } from '@/types/session'
import type { HistoryItem } from '@/types/message'

interface StudentChatViewerProps {
  userId: string
  userName: string
  onBack: () => void
}

export default function StudentChatViewer({ userId, userName, onBack }: StudentChatViewerProps) {
  const { t } = useTranslation()
  const [sessions, setSessions] = useState<SessionOut[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [selectedSession, setSelectedSession] = useState<SessionOut | null>(null)
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loadingItems, setLoadingItems] = useState(false)

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true)
    try {
      const data = await usersApi.listUserSessions(userId)
      setSessions(data)
    } finally {
      setLoadingSessions(false)
    }
  }, [userId])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const selectSession = async (session: SessionOut) => {
    setSelectedSession(session)
    setLoadingItems(true)
    try {
      const history = await sessionsApi.getHistory(session.id)
      setItems(history.items)
    } finally {
      setLoadingItems(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b p-3">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="size-4" />
        </Button>
        <h2 className="text-lg font-bold">
          {userName} - {t('chat.title')}
        </h2>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-72 shrink-0 border-r">
          <ScrollArea className="h-full">
            {loadingSessions && <div className="p-3 text-sm text-muted-foreground">{t('common.loading')}</div>}
            {!loadingSessions && sessions.length === 0 && (
              <EmptyState
                icon={MessagesSquare}
                title={t('chat.noSessions')}
                className="py-8"
              />
            )}
            <div className="space-y-1 p-2">
              {sessions.map(s => (
                <div
                  key={s.id}
                  className={`rounded-md p-2 text-sm hover:bg-accent cursor-pointer ${
                    selectedSession?.id === s.id ? 'bg-accent' : ''
                  }`}
                  onClick={() => selectSession(s)}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="size-3 shrink-0" />
                    <span className="truncate font-medium">
                      {s.title || s.project_name || t('chat.newSession')}
                    </span>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {s.mode === 'project' ? t('chat.projectMode') : t('chat.freeMode')}
                    </Badge>
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {formatRelativeTime(s.last_active_at)}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {!selectedSession && (
            <EmptyState
              icon={MessageSquarePlus}
              title={t('chat.welcomeTitle')}
            />
          )}
          {selectedSession && loadingItems && (
            <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
          )}
          {selectedSession && !loadingItems && (
            <div className="space-y-4">
              {items.map((event, idx) => {
                switch (event.type) {
                  case 'user':
                  case 'agent':
                    return <MessageBubble key={idx} message={event} />
                  case 'tool_call':
                    return <ToolCallBubble key={idx} message={event} />
                  case 'quiz':
                    return (
                      <QuizCard
                        key={idx}
                        quiz={event}
                        status={event.status as 'pending' | 'answered' | 'skipped'}
                        userAnswer={event.user_answer}
                        onSubmit={() => {}}
                        onSkip={() => {}}
                      />
                    )
                }
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
