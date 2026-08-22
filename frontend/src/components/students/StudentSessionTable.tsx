"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usersApi } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/common/Pagination";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Eye } from "lucide-react";
import { useRouter } from "next/navigation";
import type { Session, Student } from "@/lib/types";
import { SkeletonTable } from "@/components/ui/skeleton-loaders";

export function StudentSessionTable({
  studentId,
}: {
  studentId: string;
}) {
  const router = useRouter();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      usersApi.listStudents(1, 100).then((data) => {
        const s = data.items.find((s) => s.id === studentId);
        if (s) setStudent(s);
      }),
      usersApi.getSessions(studentId, page).then((data) => {
        setSessions(data.items);
        setTotal(data.total);
      }),
    ])
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [studentId, page]);

  if (loading)
    return (
      <div className="p-4">
        <SkeletonTable rows={4} columns={["2fr", "1fr", "1fr"]} />
      </div>
    );

  return (
    <div className="p-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/teacher/manage/students")}
        className="mb-4"
      >
        <ArrowLeft className="mr-2 size-4" />
        返回学生列表
      </Button>
      <div className="mb-6">
        <h1 className="text-xl font-bold">
          {student?.name} ({student?.username})
        </h1>
      </div>
      <h2 className="mb-3 text-lg font-semibold">会话记录</h2>
      {sessions.length === 0 ? (
        <p className="text-muted-foreground">暂无会话记录</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-ink/25 bg-[#fbf9f3]">
          <table className="w-full text-sm">
            <thead className="bg-paper">
              <tr>
                <th className="px-4 py-2 text-left font-medium">
                  会话标题
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  模式
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  项目
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  最后活跃
                </th>
                <th className="px-4 py-2 text-left font-medium">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id} className="border-t transition-[background-color] duration-150 hover:bg-ink/[0.03]">
                  <td className="px-4 py-2 font-medium">
                    {session.title ||
                      (session.mode === "free"
                        ? "自由学习"
                        : "项目模式")}
                  </td>
                  <td className="px-4 py-2">
                    <Badge
                      variant={
                        session.mode === "project"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {session.mode === "project" ? "项目" : "自由"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {session.project_name || "-"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(session.last_active_at).toLocaleString(
                      "zh-CN",
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/teacher/manage/students/${studentId}/sessions/${session.id}`}
                    >
                      <Button size="sm" variant="ghost">
                        <Eye className="mr-1 size-4" />
                        查看
                      </Button>
                    </Link>
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
