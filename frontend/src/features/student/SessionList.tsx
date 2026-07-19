import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { sessionsApi } from '@/api/sessions'
import { useAsync } from '@/lib/useAsync'
import { formatRelativeTime } from '@/lib/formatDate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import NewSessionDialog from './NewSessionDialog'
import type { SessionOut } from '@/types/session'

export default function SessionList() {
  const navigate = useNavigate()
  const location = useLocation()
  const [refreshKey, setRefreshKey] = useState(0)
  const { data: sessions, loading } = useAsync<SessionOut[]>(
    () => sessionsApi.list({ limit: 50 }),
    [refreshKey],
  )

  const currentId = location.pathname.match(/\/student\/sessions\/([^/]+)/)?.[1]

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <NewSessionDialog
          onCreated={s => {
            setRefreshKey(k => k + 1)
            navigate(`/student/sessions/${s.id}`)
          }}
        />
      </div>
      <ScrollArea className="flex-1">
        {loading && <div className="p-3 text-sm text-muted-foreground">加载中...</div>}
        {!loading && sessions?.length === 0 && (
          <div className="p-3 text-sm text-muted-foreground">暂无会话</div>
        )}
        <div className="space-y-1 p-2">
          {sessions?.map(s => (
            <button
              key={s.id}
              onClick={() => navigate(`/student/sessions/${s.id}`)}
              className={`w-full rounded-md p-2 text-left text-sm hover:bg-accent ${
                currentId === s.id ? 'bg-accent' : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">
                  {s.title || s.project_name || '未命名会话'}
                </span>
                <Badge variant="outline" className="shrink-0 text-xs">
                  {s.mode === 'project' ? '项目' : '自由'}
                </Badge>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {formatRelativeTime(s.last_active_at)}
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
