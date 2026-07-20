import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useDocumentsStore } from '@/stores/documents'
import { useDropzone } from 'react-dropzone'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { formatDateTime } from '@/lib/formatDate'
import { Upload, FileText, RefreshCw, Trash2 } from 'lucide-react'
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

export default function KnowledgeBase() {
  const {
    documents,
    total,
    page,
    pipelineStatus,
    loading,
    fetchPage,
    startPolling,
    stopPolling,
    uploadFile,
    insertText,
    deleteDoc,
  } = useDocumentsStore()
  const [insertOpen, setInsertOpen] = useState(false)
  const [insertTextValue, setInsertTextValue] = useState('')

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: async files => {
      if (files.length === 0) return
      try {
        await uploadFile(files[0])
        toast.success(`已上传 ${files[0].name}`)
      } catch {
        // 拦截器已 toast
      }
    },
  })

  useEffect(() => {
    fetchPage(1)
    startPolling()
    return () => stopPolling()
  }, [fetchPage, startPolling, stopPolling])

  const handleInsert = async () => {
    if (!insertTextValue.trim()) return
    try {
      await insertText(insertTextValue)
      toast.success('已插入文本')
      setInsertOpen(false)
      setInsertTextValue('')
    } catch {
      // 拦截器已 toast
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b p-3">
        <div className="flex gap-2">
          <div {...getRootProps()} className="inline-block">
            <input {...getInputProps()} />
            <Button variant="default" size="sm">
              <Upload className="mr-1 h-4 w-4" />
              {isDragActive ? '释放上传' : '上传文件'}
            </Button>
          </div>
          <Dialog open={insertOpen} onOpenChange={setInsertOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <FileText className="mr-1 h-4 w-4" />
                插入文本
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>插入文本</DialogTitle>
              </DialogHeader>
              <Textarea
                value={insertTextValue}
                onChange={e => setInsertTextValue(e.target.value)}
                placeholder="粘贴要插入知识库的文本..."
                className="min-h-40"
              />
              <DialogFooter>
                <Button variant="outline" onClick={() => setInsertOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleInsert} disabled={!insertTextValue.trim()}>
                  插入
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {pipelineStatus?.busy ? (
            <Badge variant="secondary">处理中...</Badge>
          ) : (
            <Badge variant="outline">● idle</Badge>
          )}
          <Button variant="ghost" size="sm" onClick={() => fetchPage()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4">
          {loading && <div className="text-sm text-muted-foreground">加载中...</div>}
          {!loading && documents.length === 0 && (
            <div className="text-sm text-muted-foreground">暂无文档</div>
          )}
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="p-2 text-left">文件名 / ID</th>
                  <th className="p-2 text-left">大小</th>
                  <th className="p-2 text-left">状态</th>
                  <th className="p-2 text-left">处理时间</th>
                  <th className="p-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id} className="border-t">
                    <td className="p-2">{doc.file_path || doc.id}</td>
                    <td className="p-2">
                      {doc.content_length ? `${Math.round(doc.content_length / 1024)}KB` : '-'}
                    </td>
                    <td className="p-2">
                      <Badge
                        variant={
                          doc.status === 'processed'
                            ? 'default'
                            : doc.status === 'failed'
                              ? 'destructive'
                              : 'secondary'
                        }
                      >
                        {doc.status === 'processed'
                          ? '✅ 已处理'
                          : doc.status === 'processing'
                            ? '⏳ 处理中'
                            : doc.status === 'failed'
                              ? '❌ 失败'
                              : '⌛ 等待'}
                      </Badge>
                    </td>
                    <td className="p-2">
                      {doc.updated_at ? formatDateTime(doc.updated_at) : '-'}
                    </td>
                    <td className="p-2 text-right">
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>删除文档</AlertDialogTitle>
                            <AlertDialogDescription>
                              确定删除此文档吗？此操作不可恢复。
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>取消</AlertDialogCancel>
                            <AlertDialogAction onClick={() => deleteDoc(doc.id)}>
                              确认删除
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="mt-3 flex items-center justify-end gap-2 text-sm">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => fetchPage(page - 1)}
              >
                上一页
              </Button>
              <span>
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => fetchPage(page + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
