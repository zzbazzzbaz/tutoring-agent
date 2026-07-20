import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
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
          <div className="flex h-full items-center justify-center text-muted-foreground">
            {t('chat.noSession')}
          </div>
        )}
      </div>
    </div>
  )
}
