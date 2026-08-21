// 统计分析--学情总览Dashboard
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Activity,
  Users,
  Clock,
  TrendingUp,
  GraduationCap,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { analyticsApi } from "@/lib/api/analytics";
import type {
  AnomalyStudent,
  ClassComparison,
  DashboardOverview,
  LearningTrendPoint,
} from "@/lib/types";

export default function TeacherManageAnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyStudent[]>([]);
  const [trend, setTrend] = useState<LearningTrendPoint[]>([]);
  const [classComparison, setClassComparison] = useState<ClassComparison[]>([]);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await analyticsApi.getDashboard();
        setOverview(data.overview);
        setAnomalies(data.anomalies);
        setTrend(data.trend);
        setClassComparison(data.class_comparison);
      } catch (err) {
        console.error("加载 Dashboard 失败:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        加载中...
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        暂无数据
      </div>
    );
  }

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      {/* 指标卡片 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard
          icon={<Users className="size-5" />}
          label="学生总数"
          value={overview.total_students}
          color="text-blue-600"
        />
        <StatCard
          icon={<Activity className="size-5" />}
          label="今日活跃"
          value={`${overview.active_today}/${overview.total_students}`}
          color="text-green-600"
        />
        <StatCard
          icon={<Clock className="size-5" />}
          label="周均对话"
          value={overview.weekly_avg_sessions}
          suffix="次"
          color="text-purple-600"
        />
        <StatCard
          icon={<GraduationCap className="size-5" />}
          label="累计对话"
          value={overview.total_sessions}
          color="text-indigo-600"
        />
        <StatCard
          icon={<AlertTriangle className="size-5" />}
          label="待关注"
          value={overview.pending_alert_count}
          color={overview.pending_alert_count > 0 ? "text-red-600" : "text-gray-600"}
        />
      </div>

      {/* 学习趋势 */}
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="size-4 text-muted-foreground" />
          <h3 className="font-medium">最近30天学习趋势</h3>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend}>
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
              <Line
                type="monotone"
                dataKey="active_student_count"
                name="活跃学生"
                stroke="#22c55e"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 待关注 + 班级对比 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="size-4 text-red-500" />
            <h3 className="font-medium">待关注学生 ({anomalies.length})</h3>
          </div>
          {anomalies.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              所有学生状态良好 👍
            </div>
          ) : (
            <div className="space-y-2">
              {anomalies.map((s) => (
                <AnomalyRow key={s.user_id} student={s} />
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border bg-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 className="size-4 text-muted-foreground" />
            <h3 className="font-medium">班级活跃率对比</h3>
          </div>
          {classComparison.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无班级数据
            </div>
          ) : classComparison.length === 1 ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              仅管理一个班级
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={classComparison}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="class_name" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      if (name === "活跃率")
                        return [`${Math.round(value * 100)}%`, name];
                      return [value, name];
                    }}
                  />
                  <Bar
                    dataKey="active_rate"
                    name="活跃率"
                    fill="#6366f1"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 指标卡片组件
function StatCard({
  icon,
  label,
  value,
  suffix,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  suffix?: string;
  color: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className={color}>{icon}</span>
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">
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

// 异常学生行组件
function AnomalyRow({ student }: { student: AnomalyStudent }) {
  return (
    <div className="flex items-center justify-between rounded border bg-red-50/50 px-3 py-2 dark:bg-red-950/20">
      <div className="flex items-center gap-3">
        <Link
          href={`/teacher/manage/classes/${student.class_id}/students/${student.user_id}`}
          className="font-medium hover:underline"
        >
          {student.name}
        </Link>
        <span className="text-xs text-muted-foreground">
          {student.class_name}
        </span>
      </div>
      <div className="text-right">
        <div className="text-sm font-medium text-red-600">
          {student.inactive_days}天未登录
        </div>
        {student.last_active_at && (
          <div className="text-xs text-muted-foreground">
            最后活跃:{" "}
            {new Date(student.last_active_at).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  );
}
