// 统计分析--学生分析页面
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Activity,
  Calendar,
  Clock,
  MessageSquare,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { analyticsApi } from "@/lib/api/analytics";
import type { StudentAnalysisResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";

export default function StudentAnalysisPage() {
  const params = useParams();
  const userId = params.userId as string;

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<StudentAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const result = await analyticsApi.getStudentAnalysis(userId);
        setData(result);
      } catch (err) {
        console.error("加载学生分析失败:", err);
        setError("加载失败，请重试");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        加载中...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-red-500">{error || "暂无数据"}</p>
        <Button asChild variant="outline">
          <Link href="/teacher/manage/analytics">返回总览</Link>
        </Button>
      </div>
    );
  }

  const { overview, daily_activity } = data;

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      {/* 顶部导航 */}
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="sm">
          <Link href="/teacher/manage/analytics">
            <ArrowLeft className="mr-2 size-4" />
            返回总览
          </Link>
        </Button>
        <h1 className="text-xl font-semibold">{overview.name} 的学习分析</h1>
      </div>

      {/* 基本信息卡片 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <InfoCard
          icon={<MessageSquare className="size-5 text-blue-600" />}
          label="累计对话"
          value={overview.total_sessions}
          suffix="次"
        />
        <InfoCard
          icon={<Activity className={`size-5 ${overview.weekly_sessions < 2 ? "text-yellow-600" : "text-green-600"}`} />}
          label="本周对话"
          value={overview.weekly_sessions}
          suffix="次"
          highlight={overview.weekly_sessions < 2}
          highlightColor="yellow"
        />
        <InfoCard
          icon={<Calendar className="size-5 text-green-600" />}
          label="活跃天数"
          value={overview.active_days}
          suffix="天"
        />
        <InfoCard
          icon={<Clock className="size-5 text-purple-600" />}
          label="未活跃"
          value={overview.inactive_days}
          suffix="天"
          highlight={overview.inactive_days >= 7}
        />
        <InfoCard
          icon={<Users className="size-5 text-indigo-600" />}
          label="所属班级"
          value={overview.classes.length}
          suffix="个"
        />
      </div>

      {/* 学生详情 */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 font-medium">学生信息</h3>
        <div className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
          <div>
            <span className="text-muted-foreground">学号：</span>
            <span>{overview.username}</span>
          </div>
          <div>
            <span className="text-muted-foreground">姓名：</span>
            <span>{overview.name}</span>
          </div>
          <div>
            <span className="text-muted-foreground">最后活跃：</span>
            <span>
              {overview.last_active_at
                ? new Date(overview.last_active_at).toLocaleDateString()
                : "从未活跃"}
            </span>
          </div>
        </div>
      </div>

      {/* 所属班级 */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 font-medium">所属班级</h3>
        <div className="space-y-2">
          {overview.classes.map((cls) => (
            <div
              key={cls.class_id}
              className="flex items-center justify-between rounded border px-3 py-2"
            >
              <Link
                href={`/teacher/manage/classes/${cls.class_id}`}
                className="font-medium hover:underline"
              >
                {cls.class_name}
              </Link>
              <span className="text-sm text-muted-foreground">
                加入时间: {new Date(cls.joined_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 活动趋势图 */}
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="size-4 text-muted-foreground" />
          <h3 className="font-medium">最近30天活动趋势</h3>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={daily_activity}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={4} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="session_count"
                name="对话数"
                stroke="#6366f1"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// 信息卡片组件
function InfoCard({
  icon,
  label,
  value,
  suffix,
  highlight = false,
  highlightColor = "red",
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
  highlight?: boolean;
  highlightColor?: "red" | "yellow";
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        {label}
      </div>
      <div
        className={`mt-2 text-2xl font-semibold ${
          highlight
            ? highlightColor === "yellow"
              ? "text-yellow-600"
              : "text-red-600"
            : ""
        }`}
      >
        {value}
        {suffix && (
          <span className="ml-1 text-sm font-normal text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}