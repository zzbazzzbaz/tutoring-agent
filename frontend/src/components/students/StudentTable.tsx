"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usersApi } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Download,
  KeyRound,
  Trash2,
  Eye,
} from "lucide-react";
import { StudentImportDialog } from "./StudentImportDialog";
import { toast } from "sonner";
import type { Student } from "@/lib/types";

export function StudentTable() {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [importOpen, setImportOpen] = useState(false);

  function refresh() {
    setLoading(true);
    usersApi
      .listStudents()
      .then(setStudents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  const filtered = students.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.username.toLowerCase().includes(search.toLowerCase()),
  );

  async function handleResetPassword(student: Student) {
    if (!confirm(`确定重置「${student.name}」的密码为 123456 吗？`))
      return;
    try {
      await usersApi.resetPassword(student.id);
      toast.success(`已重置 ${student.name} 的密码为 123456`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "重置失败",
      );
    }
  }

  async function handleDelete(student: Student) {
    if (!confirm(`确定删除学生「${student.name}」吗？此操作不可撤销。`))
      return;
    try {
      await usersApi.delete(student.id);
      toast.success("学生已删除");
      refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "删除失败",
      );
    }
  }

  async function handleDownloadTemplate() {
    try {
      const blob = await usersApi.downloadTemplate();
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

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">学生管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleDownloadTemplate}>
            <Download className="mr-2 size-4" />
            下载模板
          </Button>
          <Button onClick={() => setImportOpen(true)}>
            导入学生
          </Button>
        </div>
      </div>
      <Input
        placeholder="搜索学生姓名或学号..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 max-w-sm"
      />
      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">学号</th>
                <th className="px-4 py-2 text-left font-medium">姓名</th>
                <th className="px-4 py-2 text-left font-medium">
                  创建时间
                </th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((student) => (
                <tr key={student.id} className="border-t">
                  <td className="px-4 py-2">{student.username}</td>
                  <td className="px-4 py-2 font-medium">
                    {student.name}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(student.created_at).toLocaleDateString(
                      "zh-CN",
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1">
                      <Link
                        href={`/teacher/manage/students/${student.id}`}
                      >
                        <Button size="sm" variant="ghost">
                          <Eye className="mr-1 size-4" />
                          查看对话
                        </Button>
                      </Link>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleResetPassword(student)}
                      >
                        <KeyRound className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(student)}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <StudentImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={refresh}
      />
    </div>
  );
}
