// 统计分析--学情总览Dashboard
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Activity,
  Users,
  TrendingUp,
  GraduationCap,
  RefreshCw,
  Trophy,
  PieChart as PieChartIcon,
  FileDown,
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
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { analyticsApi } from "@/lib/api/analytics";
import { classesApi } from "@/lib/api/classes";
import type {
  AnomalyStudent,
  ClassComparison,
  ClassInfo,
  DashboardOverview,
  LearningTrendPoint,
  ModeCount,
  StudentRanking,
} from "@/lib/types";

export default function TeacherManageAnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyStudent[]>([]);
  const [trend, setTrend] = useState<LearningTrendPoint[]>([]);
  const [classComparison, setClassComparison] = useState<ClassComparison[]>([]);
  const [modeDistribution, setModeDistribution] = useState<ModeCount[]>([]);
  const [studentRanking, setStudentRanking] = useState<StudentRanking[]>([]);
  const [rankingSort, setRankingSort] = useState<"total_sessions" | "active_days">("total_sessions");
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [selectedClassId, setSelectedClassId] = useState("all");
  const [trendDays, setTrendDays] = useState(30);

  async function load(classId?: string, days: number = 30) {
    try {
      setError(null);
      const data = await analyticsApi.getDashboard(classId, days);
      setOverview(data.overview);
      setAnomalies(data.anomalies || []);
      setTrend(data.trend || []);
      setClassComparison(data.class_comparison || []);
      setModeDistribution(data.mode_distribution || []);
      setStudentRanking(data.student_ranking || []);
    } catch (err: any) {
      console.error("加载 Dashboard 失败:", err);
      setError(err?.message || "加载失败，请重试");
      throw err;
    }
  }

  async function handleRefresh() {
    if (refreshing || loading) return;
    setRefreshing(true);
    try {
      await load(selectedClassId === "all" ? undefined : selectedClassId, trendDays);
    } catch {
      // 刷新失败保留旧数据，错误已在 load 中记录
    } finally {
      setRefreshing(false);
    }
  }

  // 加载教师的活跃班级列表（只加载一次）
  useEffect(() => {
    classesApi
      .list(undefined, "active", undefined, 1, 100)
      .then((data) =>
        setClasses((data.items || []).filter((c) => c.status === "active"))
      )
      .catch(() => setClasses([]));
  }, []);

  // 班级切换或趋势天数变化时重新加载 dashboard（首次加载也走这里）
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load(selectedClassId === "all" ? undefined : selectedClassId, trendDays)
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedClassId, trendDays]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="flex items-center gap-2">
          <RefreshCw className="size-4 animate-spin" />
          加载中...
        </div>
      </div>
    );
  }

  if (!overview && error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
        <div className="text-red-500 text-center">
          <p className="font-medium">加载失败</p>
          <p className="text-sm text-muted-foreground mt-1">{error}</p>
        </div>
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <RefreshCw className="size-4" />
          重新加载
        </button>
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

  const currentClass = classes.find((c) => c.id === selectedClassId);
  const modeTotal = modeDistribution.reduce((s, m) => s + m.count, 0);

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      {/* 班级筛选栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">班级</span>
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-[220px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部班级</SelectItem>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.grade} {c.classname}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-sm text-muted-foreground">
            {selectedClassId === "all"
              ? `全部班级 · 共 ${classes.length} 个班级`
              : `${currentClass?.grade} ${currentClass?.classname} · ${overview.total_students} 人`}
          </div>
          <Link
            href={`/teacher/manage/analytics/report?class_id=${selectedClassId}&days=${trendDays}`}
            className="inline-flex items-center gap-2 rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
          >
            <FileDown className="size-4" />
            导出报告
          </Link>
        </div>
      </div>

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

      {/* 学习趋势 + 对话模式占比 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-8">
        {/* 学习趋势 */}
        <div className="rounded-lg border bg-card p-4 lg:col-span-6">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" />
            <h3 className="font-medium">最近{trendDays}天学习趋势</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setTrendDays(7)}
              className={`rounded px-2 py-1 text-xs ${trendDays === 7 ? "bg-primary text-primary-foreground" : "border hover:bg-accent"}`}
            >
              7天
            </button>
            <button
              onClick={() => setTrendDays(30)}
              className={`rounded px-2 py-1 text-xs ${trendDays === 30 ? "bg-primary text-primary-foreground" : "border hover:bg-accent"}`}
            >
              30天
            </button>
          </div>
        </div>
        <div className="h-64">
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={4} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="session_count"
                  name="对话数"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="active_student_count"
                  name="活跃学生"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无趋势数据
            </div>
          )}
        </div>
        </div>

        {/* 对话模式占比 */}
        <div className="rounded-lg border bg-card p-4 lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <PieChartIcon className="size-4 text-muted-foreground" />
            <h3 className="font-medium">对话模式占比</h3>
          </div>
          {modeTotal === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              暂无对话数据
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <div className="relative h-48 w-48 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={modeDistribution}
                      dataKey="count"
                      nameKey="mode"
                      innerRadius={50}
                      outerRadius={74}
                      paddingAngle={2}
                    >
                      <Cell fill="#6366f1" />
                      <Cell fill="#22c55e" />
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        const label = name === "project" ? "案例模式" : "自由模式";
                        return [`${value} 次`, label];
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-xl font-semibold">{modeTotal}</span>
                  <span className="text-xs text-muted-foreground">总对话</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
                {modeDistribution.map((m) => {
                  const pct = modeTotal > 0 ? Math.round((m.count / modeTotal) * 100) : 0;
                  const label = m.mode === "project" ? "案例模式" : "自由模式";
                  const color = m.mode === "project" ? "text-indigo-600" : "text-green-600";
                  const dotColor = m.mode === "project" ? "bg-indigo-500" : "bg-green-500";
                  return (
                    <div key={m.mode} className="flex items-center gap-2">
                      <span className={`size-3 rounded-full ${dotColor}`} />
                      <span className="text-sm text-muted-foreground">{label}</span>
                      <span className={`text-sm font-medium ${color}`}>{m.count} 次</span>
                      <span className="text-sm text-muted-foreground">({pct}%)</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 待关注 + 班级对比 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 异常预警列表 */}
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
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {anomalies.map((s) => (
                <AnomalyRow key={s.user_id} student={s} />
              ))}
            </div>
          )}
        </div>

        {/* 班级活跃率对比 */}
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

      {/* 学生活跃度排行 */}
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy className="size-4 text-muted-foreground" />
            <h3 className="font-medium">学生活跃度排行</h3>
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setRankingSort("total_sessions")}
              className={`rounded px-2 py-1 text-xs ${rankingSort === "total_sessions" ? "bg-primary text-primary-foreground" : "border hover:bg-accent"}`}
            >
              按对话数
            </button>
            <button
              onClick={() => setRankingSort("active_days")}
              className={`rounded px-2 py-1 text-xs ${rankingSort === "active_days" ? "bg-primary text-primary-foreground" : "border hover:bg-accent"}`}
            >
              按活跃天数
            </button>
          </div>
        </div>
        {studentRanking.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">暂无学生数据</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">排名</th>
                  <th className="px-4 py-2 text-left font-medium">学号</th>
                  <th className="px-4 py-2 text-left font-medium">姓名</th>
                  <th className="px-4 py-2 text-right font-medium">累计对话</th>
                  <th className="px-4 py-2 text-right font-medium">活跃天数</th>
                  <th className="px-4 py-2 text-left font-medium">最后活跃</th>
                </tr>
              </thead>
              <tbody>
                {[...studentRanking]
                  .sort((a, b) => b[rankingSort] - a[rankingSort])
                  .map((s, i) => (
                    <tr key={s.user_id} className="border-t">
                      <td className="px-4 py-2">
                        {i < 3 ? (
                          <span
                            className={`inline-flex size-6 items-center justify-center rounded-full text-xs font-bold text-white ${
                              i === 0 ? "bg-yellow-500" : i === 1 ? "bg-gray-400" : "bg-amber-600"
                            }`}
                          >
                            {i + 1}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{i + 1}</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{s.username}</td>
                      <td className="px-4 py-2">
                        <Link
                          href={`/teacher/manage/analytics/students/${s.user_id}`}
                          className="font-medium text-blue-600 hover:underline"
                        >
                          {s.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-right font-medium">{s.total_sessions}</td>
                      <td className="px-4 py-2 text-right">{s.active_days}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {s.last_active_at
                          ? new Date(s.last_active_at).toLocaleDateString("zh-CN").replace(/\//g, "-")
                          : "从未活跃"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
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
          href={`/teacher/manage/analytics/students/${student.user_id}`}
          className="font-medium hover:underline"
        >
          {student.name}
        </Link>
        <Link
          href={`/teacher/manage/classes/${student.class_id}?back=/teacher/manage/analytics`}
          className="text-xs text-blue-600 hover:underline"
        >
          {student.class_name}
        </Link>
      </div>
      <div className="text-right">
        <div className="text-sm font-medium text-red-600">
          {student.last_active_at
            ? `${student.inactive_days}天未登录`
            : "从未登录"}
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
