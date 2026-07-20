import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Trash2, MessagesSquare } from 'lucide-react'
import { useChatStore } from '@/stores/chat'
import { sessionsApi } from '@/api/sessions'
import { formatRelativeTime } from '@/lib/formatDate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import EmptyState from '@/features/shared/EmptyState'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import NewSessionDialog from './NewSessionDialog'

export default function SessionList() {
  const { t } = useTranslation()
  const sessions = useChatStore(s => s.sessions)
  const loadingSessions = useChatStore(s => s.loadingSessions)
  const loadSessions = useChatStore(s => s.loadSessions)
  const selectSession = useChatStore(s => s.selectSession)
  const currentSession = useChatStore(s => s.currentSession)

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const handleDelete = async (id: string) => {
    await sessionsApi.delete(id)
    await loadSessions()
    if (currentSession?.id === id) {
      useChatStore.getState().clearCurrent()
    }
  }

  return (
    <div className="flex h-full flex-col border-r">
      <div className="p-2">
        <NewSessionDialog />
      </div>
      <ScrollArea className="flex-1">
        {loadingSessions && <div className="p-3 text-sm text-muted-foreground">{t('common.loading')}</div>}
        {!loadingSessions && sessions.length === 0 && (
          <EmptyState
            icon={MessagesSquare}
            title={t('chat.noSessions')}
            description={t('chat.noSessionsDesc')}
            className="py-8"
          />
        )}
        <div className="space-y-1 p-2">
          {sessions.map(s => (
            <div
              key={s.id}
              className={`group flex items-center gap-2 rounded-md p-2 text-sm hover:bg-accent cursor-pointer ${
                currentSession?.id === s.id ? 'bg-accent' : ''
              }`}
              onClick={() => selectSession(s.id)}
            >
              <div className="flex-1 overflow-hidden">
                <div className="flex items-center gap-2">
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
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 opacity-0 group-hover:opacity-100"
                    onClick={e => e.stopPropagation()}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t('common.confirm')}?
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={() => handleDelete(s.id)}>
                      {t('common.delete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
