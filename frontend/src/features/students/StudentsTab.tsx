import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, RotateCcw, Trash2, MessageSquare, Download } from 'lucide-react'
import { usersApi, type ImportResult } from '@/api/users'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { formatDateTime } from '@/lib/formatDate'
import type { UserOut } from '@/types/user'
import StudentChatViewer from './StudentChatViewer'

export default function StudentsTab() {
  const { t } = useTranslation()
  const [students, setStudents] = useState<UserOut[]>([])
  const [loading, setLoading] = useState(true)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [search, setSearch] = useState('')
  const [viewingStudent, setViewingStudent] = useState<UserOut | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await usersApi.listStudents()
      setStudents(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const result = await usersApi.importStudents(file)
      setImportResult(result)
      await load()
    } catch {
      // toast handled by interceptor
    }
    e.target.value = ''
  }

  const handleReset = async (id: string) => {
    await usersApi.resetPassword(id)
    toast.success(t('students.resetPassword') + ': 123456')
  }

  const handleDelete = async (id: string) => {
    await usersApi.deleteUser(id)
    await load()
    toast.success(t('common.delete'))
  }

  const filtered = students.filter(
    s => s.username.includes(search) || s.name.includes(search)
  )

  if (viewingStudent) {
    return (
      <StudentChatViewer
        userId={viewingStudent.id}
        userName={viewingStudent.name}
        onBack={() => setViewingStudent(null)}
      />
    )
  }

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">{t('students.title')}</h2>
        <div className="flex items-center gap-2">
          <Input
            placeholder={t('common.search')}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-48"
          />
          <Button variant="outline" onClick={() => document.getElementById('import-file')?.click()}>
            <Upload className="mr-2 size-4" />
            {t('students.import')}
          </Button>
          <Button variant="outline" onClick={() => usersApi.downloadTemplate()}>
            <Download className="mr-2 size-4" />
            {t('students.downloadTemplate')}
          </Button>
          <input
            id="import-file"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={handleImport}
          />
        </div>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
        ) : filtered.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t('common.empty')}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('students.username')}</TableHead>
                <TableHead>{t('students.name')}</TableHead>
                <TableHead>{t('students.createdAt')}</TableHead>
                <TableHead className="text-right">{t('students.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(s => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono">{s.username}</TableCell>
                  <TableCell>{s.name}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(s.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => setViewingStudent(s)}
                      >
                        <MessageSquare className="size-3.5" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8">
                            <RotateCcw className="size-3.5" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t('students.resetPassword')}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t('students.resetConfirm')}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleReset(s.id)}>
                              {t('common.confirm')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8 text-destructive">
                            <Trash2 className="size-3.5" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t('students.deleteConfirm')}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(s.id)}>
                              {t('common.delete')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>

      <Dialog open={!!importResult} onOpenChange={() => setImportResult(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('students.import')}</DialogTitle>
          </DialogHeader>
          {importResult && (
            <div className="space-y-2 text-sm">
              <p>{t('students.importResult', {
                total: importResult.total,
                created: importResult.created,
                skipped: importResult.skipped,
              })}</p>
              {importResult.errors.length > 0 && (
                <div className="text-destructive">
                  {importResult.errors.map((e, i) => (
                    <p key={i}>{e}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setImportResult(null)}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
