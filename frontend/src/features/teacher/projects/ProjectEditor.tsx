import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { projectsApi } from '@/api/projects'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ProjectOut } from '@/types/project'

const MAX_NAME = 200

export default function ProjectEditor() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [name, setName] = useState('')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [backgroundMd, setBackgroundMd] = useState('')
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!id) return
    projectsApi
      .get(id)
      .then((p: ProjectOut) => {
        setName(p.name)
        setStatus(p.status)
        setBackgroundMd(p.background_md)
      })
      .finally(() => setLoading(false))
  }, [id])

  const canSave = !!name.trim() && !!backgroundMd.trim() && name.length <= MAX_NAME

  const handleSave = async () => {
    if (!canSave) return
    setSaving(true)
    try {
      if (isEdit) {
        await projectsApi.update(id!, { name, status, background_md: backgroundMd })
        toast.success('已保存')
      } else {
        await projectsApi.create({ name, status, background_md: backgroundMd })
        toast.success('已创建')
      }
      navigate('/teacher/projects')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-8 text-muted-foreground">加载中...</div>

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b p-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/teacher/projects')}>
          ← 返回列表
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/teacher/projects')}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={!canSave || saving}>
            {saving ? '保存中...' : '保存'}
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <div className="mx-auto max-w-5xl space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">名称</Label>
              <Input
                id="name"
                value={name}
                onChange={e => setName(e.target.value.slice(0, MAX_NAME))}
                placeholder="项目名称"
              />
              <div className="text-right text-xs text-muted-foreground">
                {name.length}/{MAX_NAME}
              </div>
            </div>
            <div className="space-y-2">
              <Label>状态</Label>
              <Select
                value={status}
                onValueChange={v => setStatus(v as 'draft' | 'published')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">草稿</SelectItem>
                  <SelectItem value="published">已发布</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>项目背景 (Markdown)</Label>
              <textarea
                value={backgroundMd}
                onChange={e => setBackgroundMd(e.target.value)}
                placeholder={'## 实验目标\n理解...\n\n## 实验步骤\n1. ...'}
                className="min-h-96 w-full resize-y rounded-md border bg-background p-3 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="space-y-2">
              <Label>实时预览</Label>
              <div className="min-h-96 overflow-auto rounded-md border bg-background p-3">
                {backgroundMd ? (
                  <MarkdownRenderer content={backgroundMd} />
                ) : (
                  <span className="text-sm text-muted-foreground">
                    在左侧输入 Markdown 即可看到预览
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
