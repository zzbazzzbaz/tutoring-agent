// 班级管理-班级学生页面
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { classesApi } from "@/lib/api/classes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/common/Pagination";
import {
  ArrowLeft,
  UserPlus,
  Trash2,
  Search,
  KeyRound,
  Download,
  Eye,
} from "lucide-react";
import { toast } from "sonner";
import type { ClassStudent, Student } from "@/lib/types";
import { StudentImportDialog } from "@/components/students/StudentImportDialog";

export default function ClassStudentsPage() {
  const params = useParams();
  const classId = params.classId as string;
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [showPasswords, setShowPasswords] = useState<Set<string>>(new Set());

  function refresh() {
    setLoading(true);
    classesApi
      .listStudents(classId, keyword || undefined, page)
      .then((data) => {
        setStudents(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (classId) refresh();
  }, [classId, page]);

  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      refresh();
    }, 300);
    return () => clearTimeout(t);
  }, [keyword]);

  async function handleRemove(userId: string) {
    if (!confirm("确定移除该学生吗？")) return;
    try {
      await classesApi.removeStudent(classId, userId);
      toast.success("已移除");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  }
  async function handleResetPassword(userId: string, name: string) {
    if (!confirm(`确定重置「${name}」的密码为学号后六位吗？`))
      return;
    try {
      await classesApi.resetPassword(classId, userId);
      toast.success(`已重置 ${name} 的密码为学号后六位`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "重置失败",
      );
    }
  }
    async function handleDownloadTemplate() {
    try {
      const blob = await classesApi.downloadTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "学生导入模板.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("下载模板失败");
    }
  }

  function handleAdded() {
    setShowAddDialog(false);
    refresh();
  }

  function togglePassword(userId: string) {
    setShowPasswords((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href={`/teacher/manage/classes/${classId}`}>
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-bold">班级学生管理</h1>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleDownloadTemplate}>
            <Download className="mr-2 size-4" />
            下载模板
          </Button>
          <Button onClick={() => setImportOpen(true)}>
            导入学生
          </Button>
          <Button onClick={() => setShowAddDialog(true)}>
            <UserPlus className="mr-2 size-4" />
          添加学生
          </Button>
          <Button onClick={() => setBulkDeleteOpen(true)}>
            <Trash2 className="mr-2 size-4" />
            批量删除
          </Button>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <Search className="size-4 text-muted-foreground" />
        <Input
          placeholder="搜索学生姓名或学号..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">学号</th>
                <th className="px-4 py-2 text-left font-medium">姓名</th>
                <th className="px-4 py-2 text-left font-medium">初始密码</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.user_id} className="border-t">
                  <td className="px-4 py-2">{s.username}</td>
                  <td className="px-4 py-2 font-medium">{s.name}</td>
                  <td className="px-4 py-2">
                    <span className="inline-flex items-center gap-1">
                      {showPasswords.has(s.user_id) ? s.username.slice(-6) : "••••••"}
                      <button
                        onClick={() => togglePassword(s.user_id)}
                        title="初始密码，学生改密后以自设为准"
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Eye className="size-3" />
                      </button>
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleResetPassword(s.user_id, s.name)}
                      >
                        <KeyRound className="size-4" />
                      </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleRemove(s.user_id)}
                    >
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    暂无学生
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="px-4 pb-4">
            <Pagination
              page={page}
              pageSize={20}
              total={total}
              onPageChange={setPage}
            />
          </div>
        </div>
      )}

      {showAddDialog && (
        <AddStudentsDialog
          open={showAddDialog}
          onOpenChange={setShowAddDialog}
          classId={classId}
          onAdded={handleAdded}
        />
      )}
      <StudentImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={refresh}
        classId={classId}
      />
      {bulkDeleteOpen && (
        <BulkDeleteDialog
          open={bulkDeleteOpen}
          onOpenChange={setBulkDeleteOpen}
          classId={classId}
          students={students}
          onDone={refresh}
        />
      )}
    </div>
  );
}

// 添加学生的弹窗组件
interface AddStudentsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classId: string;
  onAdded: () => void;
}

function AddStudentsDialog({ open, onOpenChange, classId, onAdded }: AddStudentsDialogProps) {
  const [allStudents, setAllStudents] = useState<Student[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      classesApi.listUnassignedStudents(1, 100).then((data) => {
        setAllStudents(data.items);
      }).catch(console.error);
    }
  }, [open]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleAdd() {
    if (selected.size === 0) {
      toast.error("请至少选择一个学生");
      return;
    }
    setLoading(true);
    try {
      const res = await classesApi.addStudents(classId, Array.from(selected));
      toast.success(`已添加 ${res.added} 个学生`);
      onAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-background p-6">
        <h2 className="mb-4 text-lg font-semibold">添加学生到班级</h2>
        <div className="mb-4 max-h-64 overflow-y-auto border rounded">
          {allStudents.map((s) => (
            <label
              key={s.id}
              className="flex cursor-pointer items-center gap-2 border-b px-3 py-2 hover:bg-muted"
            >
              <input
                type="checkbox"
                checked={selected.has(s.id)}
                onChange={() => toggle(s.id)}
              />
              <span>{s.username} - {s.name}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleAdd} disabled={loading}>
            {loading ? "添加中..." : `添加 (${selected.size})`}
          </Button>
        </div>
      </div>
    </div>
  );
}

// 批量删除弹窗组件
interface BulkDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classId: string;
  students: ClassStudent[];
  onDone: () => void;
}

function BulkDeleteDialog({ open, onOpenChange, classId, students, onDone }: BulkDeleteDialogProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showReasonInput, setShowReasonInput] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setSelected(new Set());
      setShowReasonInput(false);
      setReason("");
    }
  }, [open]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleRemove() {
    if (selected.size === 0) {
      toast.error("请至少选择一个学生");
      return;
    }
    setLoading(true);
    try {
      await classesApi.bulkRemoveStudents(classId, Array.from(selected));
      toast.success(`已从班级移除 ${selected.size} 个学生`);
      onDone();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteAccount() {
    if (!showReasonInput) {
      if (selected.size === 0) {
        toast.error("请至少选择一个学生");
        return;
      }
      setShowReasonInput(true);
      return;
    }
    if (!reason.trim()) {
      toast.error("请填写删除原因");
      return;
    }
    setLoading(true);
    try {
      await classesApi.bulkDeleteStudents(classId, Array.from(selected), reason.trim());
      toast.success(`已删除 ${selected.size} 个学生账号`);
      onDone();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-background p-6">
        <h2 className="mb-4 text-lg font-semibold">批量删除</h2>
        {!showReasonInput ? (
          <>
            <div className="mb-4 max-h-64 overflow-y-auto rounded border">
              {students.map((s) => (
                <label
                  key={s.user_id}
                  className="flex cursor-pointer items-center gap-2 border-b px-3 py-2 hover:bg-muted"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(s.user_id)}
                    onChange={() => toggle(s.user_id)}
                  />
                  <span>{s.username} - {s.name}</span>
                </label>
              ))}
              {students.length === 0 && (
                <p className="px-3 py-4 text-center text-sm text-muted-foreground">暂无学生</p>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button variant="outline" onClick={handleRemove} disabled={loading}>
                从班级移除 ({selected.size})
              </Button>
              <Button variant="destructive" onClick={handleDeleteAccount} disabled={loading}>
                删除账号 ({selected.size})
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="mb-2 text-sm text-muted-foreground">
              将删除 {selected.size} 个学生账号，请填写删除原因：
            </p>
            <Input
              placeholder="删除原因（必填）"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mb-4"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowReasonInput(false)}>
                返回
              </Button>
              <Button variant="destructive" onClick={handleDeleteAccount} disabled={loading || !reason.trim()}>
                {loading ? "删除中..." : "确认删除"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}