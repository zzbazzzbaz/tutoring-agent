import { useNavigate } from 'react-router-dom'
import { sessionsApi } from '@/api/sessions'
import { useChatStore } from '@/stores/chat'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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

export default function SessionHeader() {
  const navigate = useNavigate()
  const session = useChatStore(s => s.currentSession)
  const clearCurrent = useChatStore(s => s.clearCurrent)

  if (!session) return null

  const handleDelete = async () => {
    try {
      await sessionsApi.end(session.id)
      clearCurrent()
      navigate('/student/sessions')
    } catch {
      // toast 已由 axios 拦截器处理
    }
  }

  return (
    <div className="flex h-12 items-center justify-between border-b px-4">
      <div className="flex items-center gap-2">
        <span className="font-medium">
          {session.title || session.project_name || '未命名会话'}
        </span>
        <Badge variant="outline">
          {session.mode === 'project'
            ? `项目: ${session.project_name || ''}`
            : '自由学习'}
        </Badge>
      </div>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="ghost" size="sm">
            删除会话
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除会话</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除此会话吗？所有消息和题目记录将永久丢失。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete}>确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
