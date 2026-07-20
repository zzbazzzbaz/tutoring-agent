import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Save } from 'lucide-react'
import { projectsApi } from '@/api/projects'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import { toast } from 'sonner'
import type { ProjectOut } from '@/types/project'

interface ProjectEditorProps {
  projectId: string
  onBack: () => void
}

export default function ProjectEditor({ projectId, onBack }: ProjectEditorProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [backgroundMd, setBackgroundMd] = useState('')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [loading, setLoading] = useState(projectId !== 'new')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (projectId !== 'new') {
      setLoading(true)
      projectsApi.get(projectId).then((p: ProjectOut) => {
        setName(p.name)
        setBackgroundMd(p.background_md)
        setStatus(p.status)
      }).finally(() => setLoading(false))
    }
  }, [projectId])

  const handleSave = async () => {
    if (!name.trim() || !backgroundMd.trim()) return
    setSaving(true)
    try {
      if (projectId === 'new') {
        await projectsApi.create({ name: name.trim(), background_md: backgroundMd, status })
      } else {
        await projectsApi.update(projectId, { name: name.trim(), background_md: backgroundMd, status })
      }
      toast.success(t('common.save'))
      onBack()
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-4 text-muted-foreground">{t('common.loading')}</div>

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="size-4" />
          </Button>
          <h2 className="text-lg font-bold">
            {projectId === 'new' ? t('projects.new') : t('projects.edit')}
          </h2>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setStatus(s => s === 'draft' ? 'published' : 'draft')}
          >
            {status === 'published' ? t('projects.unpublish') : t('projects.publish')}
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="mr-2 size-4" />
            {t('common.save')}
          </Button>
        </div>
      </div>
      <div className="mb-4">
        <Label htmlFor="project-name">{t('projects.name')}</Label>
        <Input
          id="project-name"
          value={name}
          onChange={e => setName(e.target.value)}
          className="mt-1"
        />
      </div>
      <div className="grid flex-1 grid-cols-2 gap-4 overflow-hidden">
        <div className="flex flex-col">
          <Label>{t('projects.background')}</Label>
          <Textarea
            value={backgroundMd}
            onChange={e => setBackgroundMd(e.target.value)}
            className="mt-1 flex-1 resize-none font-mono text-sm"
            placeholder="Markdown..."
          />
        </div>
        <div className="flex flex-col">
          <Label>{t('projects.preview')}</Label>
          <ScrollArea className="mt-1 flex-1 rounded-md border p-3">
            <MarkdownRenderer content={backgroundMd || '*预览为空*'} />
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
