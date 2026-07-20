import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { projectsApi } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { formatDateTime } from '@/lib/formatDate'
import { toast } from 'sonner'
import type { ProjectOut } from '@/types/project'
import ProjectEditor from './ProjectEditor'

export default function ProjectsTab() {
  const { t } = useTranslation()
  const user = useAuthStore(s => s.user)
  const isTeacher = user?.role === 'teacher'
  const [projects, setProjects] = useState<ProjectOut[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [editingId, setEditingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await projectsApi.list(statusFilter === 'all' ? undefined : statusFilter)
      setProjects(data)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    load()
  }, [load])

  const handleDelete = async (id: string) => {
    await projectsApi.delete(id)
    await load()
    toast.success(t('common.delete'))
  }

  if (editingId) {
    return <ProjectEditor projectId={editingId} onBack={() => { setEditingId(null); load() }} />
  }

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">{t('projects.title')}</h2>
        {isTeacher && (
          <Button onClick={() => setEditingId('new')}>
            <Plus className="mr-2 size-4" />
            {t('projects.new')}
          </Button>
        )}
      </div>
      <div className="mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('common.all')}</SelectItem>
            <SelectItem value="draft">{t('projects.draft')}</SelectItem>
            <SelectItem value="published">{t('projects.published')}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
        ) : projects.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t('common.empty')}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('projects.name')}</TableHead>
                <TableHead>{t('projects.status')}</TableHead>
                <TableHead>{t('projects.updatedAt')}</TableHead>
                {isTeacher && <TableHead className="text-right">{t('projects.actions')}</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map(p => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>
                    <Badge variant={p.status === 'published' ? 'default' : 'secondary'}>
                      {p.status === 'published' ? t('projects.published') : t('projects.draft')}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(p.updated_at)}</TableCell>
                  {isTeacher && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="size-8" onClick={() => setEditingId(p.id)}>
                          <Pencil className="size-3.5" />
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="size-8 text-destructive">
                              <Trash2 className="size-3.5" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                              <AlertDialogDescription>{t('common.confirm')}?</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(p.id)}>
                                {t('common.delete')}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>
    </div>
  )
}
