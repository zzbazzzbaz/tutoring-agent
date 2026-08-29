"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usersApi } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/common/Pagination";
import { Input } from "@/components/ui/input";
import {
  Download,
  KeyRound,
  Trash2,
  Eye,
} from "lucide-react";
import { StudentImportDialog } from "./StudentImportDialog";
import { toast } from "sonner";
import { SkeletonTable } from "@/components/ui/skeleton-loaders";
import type { Student } from "@/lib/types";

export function StudentTable() {
  const [students, setStudents] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [importOpen, setImportOpen] = useState(false);

  function refresh() {
    setLoading(true);
    usersApi
      .listStudents(page)
      .then((data) => {
        setStudents(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, [page]);

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
          <Button
            variant="ghost"
            size="sm"
            className="bg-gradient-to-r from-[#0b3d31] to-[#064e3b] text-emerald-50 shadow-sm hover:from-[#0b3d31] hover:to-[#064e3b]"
            onClick={() => setImportOpen(true)}
          >
            导入学生
          </Button>
        </div>
      </div>
      <Input
        placeholder="搜索学生姓名或学号..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 max-w-sm !border-ink/25"
      />
      {loading ? (
        <SkeletonTable rows={5} columns={["2fr", "1fr", "1fr", "1fr"]} />
      ) : (
        <div className="overflow-hidden rounded-md border border-ink/25 bg-paper-card">
          <table className="w-full text-sm">
            <thead className="bg-paper">
              <tr>
                <th className="px-4 py-2 text-left font-medium">学号</th>
                <th className="px-4 py-2 text-left font-medium">姓名</th>
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
      <StudentImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={refresh}
      />
    </div>
  );
}
