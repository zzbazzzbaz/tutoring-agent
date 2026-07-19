import { useState } from 'react'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { projectsApi } from '@/api/projects'
import { useAsync } from '@/lib/useAsync'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { SessionOut } from '@/types/session'
import type { ProjectOut } from '@/types/project'

interface Props {
  onCreated: (s: SessionOut) => void
}

export default function NewSessionDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'free' | 'project'>('free')
  const [projectId, setProjectId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const { data: publishedProjects } = useAsync<ProjectOut[]>(
    () => (open ? projectsApi.list('published') : Promise.resolve([])),
    [open],
  )

  const handleStart = async () => {
    if (mode === 'project' && !projectId) {
      toast.error('请选择一个项目')
      return
    }
    setCreating(true)
    try {
      const session = await sessionsApi.create({
        mode,
        project_id: mode === 'project' ? projectId : undefined,
      })
      onCreated(session)
      setOpen(false)
      setMode('free')
      setProjectId(null)
    } finally {
      setCreating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="w-full">+ 新建会话</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建会话</DialogTitle>
          <DialogDescription>选择会话模式开始学习</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>模式</Label>
            <RadioGroup
              value={mode}
              onValueChange={v => setMode(v as 'free' | 'project')}
              className="flex gap-6"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="free" id="m-free" />
                <Label htmlFor="m-free">自由学习</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="project" id="m-project" />
                <Label htmlFor="m-project">项目学习</Label>
              </div>
            </RadioGroup>
          </div>
          {mode === 'project' && (
            <div className="space-y-2">
              <Label>选择项目</Label>
              <Select value={projectId || ''} onValueChange={setProjectId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择一个已发布项目..." />
                </SelectTrigger>
                <SelectContent>
                  {publishedProjects?.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {publishedProjects?.length === 0 && (
                <p className="text-xs text-muted-foreground">暂无已发布项目</p>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={handleStart} disabled={creating}>
            {creating ? '创建中...' : '开始会话'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
