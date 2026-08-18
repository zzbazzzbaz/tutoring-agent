// 班级列表组件

"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { classesApi } from "@/lib/api/classes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/common/Pagination";
import { ClassFormDialog } from "./ClassFormDialog";
import { Trash2, Pencil, Users } from "lucide-react";
import { toast } from "sonner";
import type { ClassInfo } from "@/lib/types";

export function ClassList() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingClass, setEditingClass] = useState<ClassInfo | null>(null);

  function refresh() {
    setLoading(true);
    classesApi
      .list(undefined, undefined, keyword || undefined, page)
      .then((data) => {
        setClasses(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, [page]);

  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      refresh();
    }, 300);
    return () => clearTimeout(t);
  }, [keyword]);

  async function handleDelete(cls: ClassInfo) {
    if (!confirm(`确定删除班级「${cls.grade}${cls.classname}」吗？`)) return;
    try {
      await classesApi.delete(cls.id);
      toast.success("班级已删除");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  function handleEdit(cls: ClassInfo) {
    setEditingClass(cls);
    setDialogOpen(true);
  }

  function handleCreate() {
    setEditingClass(null);
    setDialogOpen(true);
  }

  function handleSaved() {
    setDialogOpen(false);
    setEditingClass(null);
    refresh();
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">班级管理</h1>
        <Button onClick={handleCreate}>
          <Users className="mr-2 size-4" />
          新建班级
        </Button>
      </div>

      <Input
        placeholder="搜索班级..."
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="mb-4 max-w-sm"
      />

      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">年级</th>
                <th className="px-4 py-2 text-left font-medium">班级名称</th>
                <th className="px-4 py-2 text-left font-medium">授课教师</th>
                <th className="px-4 py-2 text-left font-medium">学生数</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">创建时间</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((cls) => (
                <tr key={cls.id} className="border-t">
                  <td className="px-4 py-2">{cls.grade}</td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/teacher/manage/classes/${cls.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {cls.classname}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {cls.teacher_name || "-"}
                  </td>
                  <td className="px-4 py-2">{cls.student_count}</td>
                  <td className="px-4 py-2">
                    <Badge variant={cls.status === "active" ? "default" : "secondary"}>
                      {cls.status === "active" ? "活跃" : "已归档"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(cls.created_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => handleEdit(cls)}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(cls)}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {classes.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    暂无班级
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

      <ClassFormDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditingClass(null);
        }}
        classData={editingClass}
        onSaved={handleSaved}
      />
    </div>
  );
}