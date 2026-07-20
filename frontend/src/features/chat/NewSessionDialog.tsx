import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { sessionsApi } from '@/api/sessions'
import { projectsApi } from '@/api/projects'
import { useChatStore } from '@/stores/chat'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ProjectOut } from '@/types/project'

export default function NewSessionDialog() {
  const { t } = useTranslation()
  const loadSessions = useChatStore(s => s.loadSessions)
  const selectSession = useChatStore(s => s.selectSession)
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'free' | 'project'>('free')
  const [projects, setProjects] = useState<ProjectOut[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')

  useEffect(() => {
    if (open && mode === 'project') {
      projectsApi.list('published').then(setProjects)
    }
  }, [open, mode])

  const handleCreate = async () => {
    const session = await sessionsApi.create({
      mode,
      ...(mode === 'project' && selectedProject ? { project_id: selectedProject } : {}),
    })
    await loadSessions()
    await selectSession(session.id)
    setOpen(false)
    setMode('free')
    setSelectedProject('')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          {t('chat.newSession')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('chat.newSession')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant={mode === 'free' ? 'default' : 'outline'}
              className="flex-1"
              onClick={() => setMode('free')}
            >
              {t('chat.freeMode')}
            </Button>
            <Button
              variant={mode === 'project' ? 'default' : 'outline'}
              className="flex-1"
              onClick={() => setMode('project')}
            >
              {t('chat.projectMode')}
            </Button>
          </div>
          {mode === 'project' && (
            <div className="space-y-2">
              <Label>{t('chat.selectProject')}</Label>
              <Select value={selectedProject} onValueChange={setSelectedProject}>
                <SelectTrigger>
                  <SelectValue placeholder={t('chat.selectProject')} />
                </SelectTrigger>
                <SelectContent>
                  {projects.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button onClick={handleCreate} className="w-full">
            {t('common.confirm')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
