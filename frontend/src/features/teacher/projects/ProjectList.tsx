import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { projectsApi } from '@/api/projects'
import { useAsync } from '@/lib/useAsync'
import { formatDateTime } from '@/lib/formatDate'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
import { Plus, Pencil, Trash2 } from 'lucide-react'
import type { ProjectOut } from '@/types/project'

export default function ProjectList() {
  const navigate = useNavigate()
  const [refreshKey, setRefreshKey] = useState(0)
  const { data: projects, loading } = useAsync<ProjectOut[]>(
    () => projectsApi.list(),
    [refreshKey],
  )

  const toggleStatus = async (p: ProjectOut) => {
    try {
      await projectsApi.update(p.id, {
        status: p.status === 'published' ? 'draft' : 'published',
      })
      toast.success(p.status === 'published' ? '已取消发布' : '已发布')
      setRefreshKey(k => k + 1)
    } catch {
      // 拦截器已 toast
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await projectsApi.delete(id)
      toast.success('已删除')
      setRefreshKey(k => k + 1)
    } catch {
      // 拦截器已 toast
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b p-3">
        <h2 className="text-lg font-medium">项目配置</h2>
        <Button size="sm" onClick={() => navigate('/teacher/projects/new')}>
          <Plus className="mr-1 h-4 w-4" />
          新建项目
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {loading && <div className="text-sm text-muted-foreground">加载中...</div>}
        {!loading && projects?.length === 0 && (
          <div className="text-sm text-muted-foreground">暂无项目</div>
        )}
        <div className="overflow-hidden rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects?.map(p => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>
                    <Badge variant={p.status === 'published' ? 'default' : 'secondary'}>
                      {p.status === 'published' ? '已发布' : '草稿'}
                    </Badge>
                  </TableCell>
                  <TableCell>{formatDateTime(p.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/teacher/projects/${p.id}/edit`)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => toggleStatus(p)}>
                      {p.status === 'published' ? '取消发布' : '发布'}
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>删除项目</AlertDialogTitle>
                          <AlertDialogDescription>
                            确定删除项目 &quot;{p.name}&quot; 吗？此操作不可恢复。
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>取消</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(p.id)}>
                            确认删除
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}
