"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { projectsApi } from "@/lib/api/projects";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/common/Pagination";
import { Badge } from "@/components/ui/badge";
import {
  Plus,
  Pencil,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import type { Project } from "@/lib/types";

export function ProjectTable() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    projectsApi
      .list(undefined, page)
      .then((data) => {
        setProjects(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, [page]);

  async function handleDelete(project: Project) {
    if (!confirm(`确定删除项目「${project.name}」吗？`)) return;
    try {
      await projectsApi.delete(project.id);
      toast.success("项目已删除");
      refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "删除失败",
      );
    }
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">项目管理</h1>
        <Button asChild>
          <Link href="/teacher/manage/projects/new">
            <Plus className="mr-2 size-4" />
            新建项目
          </Link>
        </Button>
      </div>
      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">
                  项目名称
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  状态
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  创建时间
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} className="border-t">
                  <td className="px-4 py-2">
                    <Link
                      href={`/teacher/manage/projects/${project.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <Badge
                      variant={
                        project.status === "published"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {project.status === "published"
                        ? "已发布"
                        : "草稿"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(project.created_at).toLocaleDateString(
                      "zh-CN",
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" asChild>
                        <Link href={`/teacher/manage/projects/${project.id}/edit`}>
                          <Pencil className="size-4" />
                        </Link>
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(project)}
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
    </div>
  );
}
