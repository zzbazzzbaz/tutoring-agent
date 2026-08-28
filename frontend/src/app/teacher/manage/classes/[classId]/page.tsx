// 班级管理-超链接:班级详细页面
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { classesApi } from "@/lib/api/classes";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  MessageSquare,
  Activity,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";
import type { ClassInfo, ClassStats } from "@/lib/types";

export default function ClassDetailPage() {
  const params = useParams();
  const classId = params.classId as string;
  const [cls, setCls] = useState<ClassInfo | null>(null);
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!classId) return;
    setLoading(true);
    Promise.all([
      classesApi.get(classId),
      classesApi.getStats(classId),
    ])
      .then(([c, s]) => {
        setCls(c);
        setStats(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [classId]);

  if (loading) return <p className="p-4">加载中...</p>;
  if (!cls) return <p className="p-4 text-muted-foreground">班级不存在</p>;

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href="/teacher/manage/classes">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-bold">
            {cls.grade} {cls.classname}
          </h1>
          <Badge variant={cls.status === "active" ? "default" : "secondary"}>
            {cls.status === "active" ? "活跃" : "已归档"}
          </Badge>
        </div>
      </div>

      {stats && (
        <div className="mb-6 grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                <Users className="size-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">学生总数</p>
                <p className="text-2xl font-bold">{stats.total_students}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
                <MessageSquare className="size-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">会话总数</p>
                <p className="text-2xl font-bold">{stats.total_sessions}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100 text-orange-600">
                <Activity className="size-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">今日活跃</p>
                <p className="text-2xl font-bold">{stats.active_today}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">班级学生</CardTitle>
          </CardHeader>
          <CardContent>
            <Link
              href={`/teacher/manage/classes/${classId}/students`}
              className="text-primary hover:underline"
            >
              查看全部学生 →
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">对话记录</CardTitle>
          </CardHeader>
          <CardContent>
            <Link
              href={`/teacher/manage/classes/${classId}/sessions`}
              className="text-primary hover:underline"
            >
              查看全部对话 →
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}