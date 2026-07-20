import { useTranslation } from 'react-i18next'
import { MessageSquarePlus } from 'lucide-react'
import { useChatStore } from '@/stores/chat'
import EmptyState from '@/features/shared/EmptyState'
import SessionList from './SessionList'
import ChatView from './ChatView'

export default function ChatTab() {
  const { t } = useTranslation()
  const currentSession = useChatStore(s => s.currentSession)

  return (
    <div className="flex h-full">
      <div className="w-72 shrink-0">
        <SessionList />
      </div>
      <div className="flex-1">
        {currentSession ? (
          <ChatView />
        ) : (
          <EmptyState
            icon={MessageSquarePlus}
            title={t('chat.welcomeTitle')}
            description={t('chat.welcomeDesc')}
          />
        )}
      </div>
    </div>
  )
}
