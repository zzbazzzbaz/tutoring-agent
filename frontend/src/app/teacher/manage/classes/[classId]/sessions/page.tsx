// 班级管理-班级对话记录页面
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { classesApi } from "@/lib/api/classes";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pagination } from "@/components/common/Pagination";
import { ArrowLeft, Eye, Search } from "lucide-react";
import type { ClassSession } from "@/lib/types";

export default function ClassSessionsPage() {
  const params = useParams();
  const classId = params.classId as string;
  const [sessions, setSessions] = useState<ClassSession[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [mode, setMode] = useState("all");
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    classesApi
      .listSessions(
        classId,
        mode === "all" ? undefined : mode,
        keyword || undefined,
        page,
      )
      .then((data) => {
        setSessions(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  // 页码/模式变化时直接刷新
  useEffect(() => {
    if (classId) refresh();
  }, [classId, page, mode]);

  // 关键字输入 300ms 防抖后刷新，并重置回第 1 页
  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      refresh();
    }, 300);
    return () => clearTimeout(t);
  }, [keyword]);

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center gap-3">
        <Button asChild variant="ghost" size="sm">
          <Link href={`/teacher/manage/classes/${classId}`}>
            <ArrowLeft className="size-4" />
          </Link>
        </Button>
        <h1 className="text-xl font-bold">班级对话记录</h1>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="搜索学生姓名或学号..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="max-w-sm pl-8"
          />
        </div>
        <Select value={mode} onValueChange={setMode}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="全部模式" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部模式</SelectItem>
            <SelectItem value="project">项目模式</SelectItem>
            <SelectItem value="free">自由模式</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">学号</th>
                <th className="px-4 py-2 text-left font-medium">学生</th>
                <th className="px-4 py-2 text-left font-medium">会话标题</th>
                <th className="px-4 py-2 text-left font-medium">模式</th>
                <th className="px-4 py-2 text-left font-medium">项目</th>
                <th className="px-4 py-2 text-left font-medium">最后活跃</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2 text-muted-foreground">
                    {s.username || "-"}
                  </td>
                  <td className="px-4 py-2">{s.user_name || s.user_id}</td>
                  <td className="px-4 py-2">{s.title || "（无标题）"}</td>
                  <td className="px-4 py-2">
                    <Badge variant={s.mode === "project" ? "default" : "secondary"}>
                      {s.mode === "project" ? "项目模式" : "自由模式"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {s.project_name || "-"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(s.last_active_at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-2">
                    <Link href={`/teacher/manage/students/${s.user_id}`}>
                      <Button size="sm" variant="ghost">
                        <Eye className="mr-1 size-4" />
                        查看
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-muted-foreground"
                  >
                    暂无对话记录
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
    </div>
  );
}
