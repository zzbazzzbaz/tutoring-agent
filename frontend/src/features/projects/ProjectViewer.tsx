import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft } from 'lucide-react'
import { projectsApi } from '@/api/projects'
import { Button } from '@/components/ui/button'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { ProjectOut } from '@/types/project'

interface ProjectViewerProps {
  projectId: string
  onBack: () => void
}

export default function ProjectViewer({ projectId, onBack }: ProjectViewerProps) {
  const { t } = useTranslation()
  const [project, setProject] = useState<ProjectOut | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    projectsApi.get(projectId).then(p => setProject(p)).finally(() => setLoading(false))
  }, [projectId])

  if (loading) return <div className="p-4 text-muted-foreground">{t('common.loading')}</div>
  if (!project) return null

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="size-4" />
        </Button>
        <h2 className="text-lg font-bold">{project.name}</h2>
      </div>
      <ScrollArea className="flex-1 rounded-md border p-6">
        <MarkdownRenderer content={project.background_md} />
      </ScrollArea>
    </div>
  )
}
