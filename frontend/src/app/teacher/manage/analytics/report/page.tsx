// 统计分析--导出报告页
"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  AlertTriangle,
  Activity,
  Users,
  Clock,
  GraduationCap,
  RefreshCw,
  TrendingUp,
  Trophy,
  PieChart as PieChartIcon,
  Printer,
  BarChart3,
  MessageSquare,
  Bot,
  Repeat,
  Target,
} from "lucide-react";
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
  KeyStudent,
  LearningTrendPoint,
  MessageStats,
  ModeCount,
  StudentRanking,
} from "@/lib/types";

const DAYS_OPTIONS = [7, 30] as const;
type DaysOption = (typeof DAYS_OPTIONS)[number];

function ReportPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyStudent[]>([]);
  const [trend, setTrend] = useState<LearningTrendPoint[]>([]);
  const [classComparison, setClassComparison] = useState<ClassComparison[]>([]);
  const [modeDistribution, setModeDistribution] = useState<ModeCount[]>([]);
  const [studentRanking, setStudentRanking] = useState<StudentRanking[]>([]);
  const [messageStats, setMessageStats] = useState<MessageStats | null>(null);
  const [keyStudents, setKeyStudents] = useState<KeyStudent[]>([]);
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [selectedClassId, setSelectedClassId] = useState(
    () => searchParams.get("class_id") ?? "all"
  );
  const [days, setDays] = useState<DaysOption>(() => {
    const raw = Number(searchParams.get("days"));
    return (DAYS_OPTIONS as readonly number[]).includes(raw) ? (raw as DaysOption) : 30;
  });
  const [refreshing, setRefreshing] = useState(false);
  // LLM 研究摘要：成功则为 AI 摘要文本；失败(null)回退规则摘要
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);

  // 同步 URL 参数，便于打印/分享固定视图
  function syncUrl(classId: string, d: DaysOption) {
    const params = new URLSearchParams();
    if (classId !== "all") params.set("class_id", classId);
    params.set("days", String(d));
    router.replace(`/teacher/manage/analytics/report?${params.toString()}`, {
      scroll: false,
    });
  }

  function handleClassChange(classId: string) {
    setSelectedClassId(classId);
    syncUrl(classId, days);
  }

  function handleDaysChange(d: DaysOption) {
    setDays(d);
    syncUrl(selectedClassId, d);
  }

  async function load(classId?: string, d: number = 30) {
    try {
      setError(null);
      const data = await analyticsApi.getDashboard(classId, d);
      setOverview(data.overview);
      setAnomalies(data.anomalies || []);
      setTrend(data.trend || []);
      setClassComparison(data.class_comparison || []);
      setModeDistribution(data.mode_distribution || []);
      setStudentRanking(data.student_ranking || []);
      setMessageStats(data.message_stats || null);
      setKeyStudents(data.key_students || []);
    } catch (err: any) {
      console.error("加载报告数据失败:", err);
      setError(err?.message || "加载失败，请重试");
      throw err;
    }
  }

  async function handleRefresh() {
    if (refreshing || loading) return;
    setRefreshing(true);
    try {
      await load(selectedClassId === "all" ? undefined : selectedClassId, days);
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

  // 班级或天数变化时重新加载
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load(selectedClassId === "all" ? undefined : selectedClassId, days)
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClassId, days]);

  // LLM 研究摘要：独立请求，失败(503/异常)时回退规则摘要，不影响报告主体
  useEffect(() => {
    let cancelled = false;
    setSummaryLoading(true);
    analyticsApi
      .getDashboardSummary(selectedClassId === "all" ? undefined : selectedClassId, days)
      .then((data) => {
        if (!cancelled) {
          setAiSummary(data.summary);
          setSummaryUnavailable(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAiSummary(null);
          setSummaryUnavailable(true);
        }
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClassId, days]);

  const currentClass = classes.find((c) => c.id === selectedClassId);
  const modeTotal = useMemo(
    () => modeDistribution.reduce((s, m) => s + m.count, 0),
    [modeDistribution]
  );
  const projectCount =
    modeDistribution.find((m) => m.mode === "project")?.count ?? 0;
  const freeCount =
    modeDistribution.find((m) => m.mode === "free")?.count ?? 0;

  // 三日滑动均值（自然日滑动：当天+前2天窗口，开头第1/2天按已有天数平均）
  const trendRows = useMemo(() => {
    return trend.map((t, i) => {
      const win = trend.slice(Math.max(0, i - 2), i + 1);
      const avg = win.reduce((s, x) => s + x.session_count, 0) / win.length;
      return { ...t, avg3: Math.round(avg * 10) / 10 };
    });
  }, [trend]);

  // 峰值：session_count 最大者，并列取较新的（从前往后遍历用 >=）
  const peak = useMemo(() => {
    if (trend.length === 0) return null;
    return trend.reduce<LearningTrendPoint>((best, t) => {
      return t.session_count >= best.session_count ? t : best;
    }, trend[0]);
  }, [trend]);

  const activeDays = useMemo(
    () => trend.filter((t) => t.session_count > 0).length,
    [trend]
  );
  const dailyAvg = trend.length > 0 ? overview!.total_sessions / trend.length : 0;

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

  const startDate = trend.length > 0 ? trend[0].date : "";
  const endDate = trend.length > 0 ? trend[trend.length - 1].date : "";
  const generatedAt = new Date().toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  // 规则版数据摘要
  function buildSummary() {
    const parts: string[] = [];
    parts.push(
      `本期统计范围为 ${startDate} 至 ${endDate}（${days} 天），覆盖 ${
        selectedClassId === "all" ? `${classes.length} 个班级` : `${currentClass?.grade ?? ""} ${currentClass?.classname ?? ""}`
      }。`
    );
    parts.push(
      `期间累计对话 ${overview!.total_sessions} 次，日均 ${dailyAvg.toFixed(1)} 次，周均 ${overview!.weekly_avg_sessions} 次。`
    );
    if (peak && peak.session_count > 0) {
      parts.push(
        `${activeDays} 天有学生互动，互动峰值出现在 ${peak.date}（${peak.session_count} 次）。`
      );
    } else {
      parts.push("统计窗口内暂无对话记录。");
    }
    if (modeTotal > 0) {
      const mainMode = projectCount >= freeCount ? "项目模式" : "自由模式";
      const mainPct = Math.round((Math.max(projectCount, freeCount) / modeTotal) * 100);
      parts.push(`对话以${mainMode}为主（占 ${mainPct}%）。`);
    }
    parts.push(
      overview!.pending_alert_count > 0
        ? `当前有 ${overview!.pending_alert_count} 名学生需要重点关注，建议及时跟进。`
        : "当前无待关注学生。"
    );
    if (messageStats && messageStats.total_messages > 0) {
      parts.push(
        `消息级互动：总互动 ${messageStats.total_messages} 条（学生发起 ${messageStats.student_messages}，AI 回复 ${messageStats.assistant_messages}），平均每会话 ${messageStats.avg_turns} 轮，知识命中率 ${Math.round(
          messageStats.knowledge_hit_rate * 100
        )}%。`
      );
    }
    return parts.join("");
  }

  const summaryText = buildSummary();

  return (
    <div className="h-full overflow-y-auto p-6 print:overflow-visible print:p-0">
      {/* 工具栏（打印时隐藏） */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Link
            href="/teacher/manage/analytics"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            返回学情总览
          </Link>
          <Select value={selectedClassId} onValueChange={handleClassChange}>
            <SelectTrigger className="w-[200px]">
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
          <div className="flex items-center gap-1">
            {DAYS_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => handleDaysChange(d)}
                className={`rounded px-2 py-1 text-xs ${
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "border hover:bg-accent"
                }`}
              >
                {d}天
              </button>
            ))}
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
        >
          <Printer className="size-4" />
          导出 PDF
        </button>
      </div>

      {/* 报告正文：始终白底黑字，打印友好 */}
      <div className="mx-auto max-w-4xl space-y-6 bg-white p-6 text-gray-900 shadow-sm print:max-w-none print:space-y-5 print:p-0 print:shadow-none">
        {/* 1. 报告头 */}
        <header className="border-b-2 border-emerald-700 pb-4">
          <h1 className="text-2xl font-bold text-gray-900">使用统计报告</h1>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-600">
            <span>
              统计范围：{startDate || "-"} 至 {endDate || "-"}
            </span>
            <span>生成时间：{generatedAt}</span>
            <span>
              班级：
              {selectedClassId === "all"
                ? `全部班级（共 ${classes.length} 个）`
                : `${currentClass?.grade ?? ""} ${currentClass?.classname ?? ""}`}
            </span>
          </div>
        </header>

        {/* 2. 核心指标 */}
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">一、核心指标</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatCard icon={<Users className="size-4" />} label="学生总数" value={overview.total_students} />
            <StatCard icon={<Activity className="size-4" />} label="今日活跃" value={`${overview.active_today}/${overview.total_students}`} />
            <StatCard icon={<Clock className="size-4" />} label="周均对话" value={`${overview.weekly_avg_sessions} 次`} />
            <StatCard icon={<GraduationCap className="size-4" />} label="累计对话" value={`${overview.total_sessions} 次`} />
            <StatCard
              icon={<AlertTriangle className="size-4" />}
              label="待关注"
              value={overview.pending_alert_count}
              highlight={overview.pending_alert_count > 0}
            />
          </div>
        </section>

        {/* 3. 互动明细（消息级，自 message 表启用后累积） */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <MessageSquare className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">二、互动明细</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatCard icon={<MessageSquare className="size-4" />} label="总互动" value={messageStats?.total_messages ?? 0} />
            <StatCard icon={<Users className="size-4" />} label="学生发起" value={messageStats?.student_messages ?? 0} />
            <StatCard icon={<Bot className="size-4" />} label="AI回复(轮次)" value={messageStats?.assistant_messages ?? 0} />
            <StatCard icon={<Repeat className="size-4" />} label="平均轮次" value={messageStats ? `${messageStats.avg_turns} 轮` : "-"} />
            <StatCard icon={<Target className="size-4" />} label="知识命中率" value={messageStats ? `${Math.round(messageStats.knowledge_hit_rate * 100)}%` : "-"} />
          </div>
          <p className="mt-2 text-xs text-gray-400">
            【口径注释】互动明细基于 message 表统计，自本版本启用后开始累积，历史会话无消息数据，短期内显示 0/暂无属正常冷启动。平均轮次 = AI 回复数 ÷ 窗口内产生过消息的会话数；知识命中率 = 命中知识库的学生提问 ÷ 学生提问总数。
          </p>
        </section>

        {/* 4. 数据摘要 */}
        <section>
          <h2 className="mb-2 text-base font-semibold text-gray-900">三、数据摘要</h2>
          {summaryLoading ? (
            <p className="flex items-center gap-2 text-sm text-gray-400">
              <RefreshCw className="size-3.5 animate-spin" />
              AI 摘要生成中...
            </p>
          ) : (
            <p className="text-sm leading-relaxed text-gray-700">{aiSummary ?? summaryText}</p>
          )}
          {aiSummary ? (
            <p className="mt-1 text-xs text-gray-400">（本摘要由 AI 智能生成）</p>
          ) : (
            <p className="mt-1 text-xs text-gray-400">
              （本摘要由规则自动生成
              {summaryUnavailable
                ? "；AI 摘要暂不可用：DASHSCOPE_API_KEY 未配置或服务异常"
                : ""}
              ）
            </p>
          )}
        </section>

        {/* 4. 趋势概览 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <TrendingUp className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">四、趋势概览</h2>
          </div>
          <div className="mb-3 grid grid-cols-3 gap-3 text-sm">
            <MiniStat label="互动峰值" value={peak && peak.session_count > 0 ? `${peak.date} · ${peak.session_count} 次` : "暂无"} />
            <MiniStat label="有互动天数" value={`${activeDays} 天`} />
            <MiniStat label="日均对话" value={`${dailyAvg.toFixed(1)} 次`} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-100 text-left text-gray-600">
                  <th className="px-3 py-2 font-medium">日期</th>
                  <th className="px-3 py-2 text-right font-medium">对话数</th>
                  <th className="px-3 py-2 text-right font-medium">活跃学生</th>
                  <th className="px-3 py-2 text-right font-medium">三日滑动均值</th>
                </tr>
              </thead>
              <tbody>
                {trendRows.map((row) => (
                  <tr key={row.date} className="border-t border-gray-200">
                    <td className="px-3 py-1.5">{row.date}</td>
                    <td className="px-3 py-1.5 text-right">{row.session_count}</td>
                    <td className="px-3 py-1.5 text-right">{row.active_student_count}</td>
                    <td className="px-3 py-1.5 text-right">{row.avg3}</td>
                  </tr>
                ))}
                {trendRows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-gray-400">
                      暂无趋势数据
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            【口径注释】三日滑动均值按自然日滑动计算：每个日期取「当天 + 前 2 天」窗口内对话数的平均，开头第 1/2 天按已有天数平均。若后端将该密集日序列改为稀疏数组，本均值将静默退化为「滚动 N 条」，需同步前端。
          </p>
        </section>

        {/* 5. 对话模式分布 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <PieChartIcon className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">五、对话模式分布</h2>
          </div>
          {modeTotal === 0 ? (
            <p className="text-sm text-gray-400">暂无对话数据</p>
          ) : (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-20 text-gray-600">项目模式</span>
                <span className="font-medium">{projectCount} 次</span>
                <span className="text-gray-500">
                  （{Math.round((projectCount / modeTotal) * 100)}%）
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-20 text-gray-600">自由模式</span>
                <span className="font-medium">{freeCount} 次</span>
                <span className="text-gray-500">
                  （{Math.round((freeCount / modeTotal) * 100)}%）
                </span>
              </div>
            </div>
          )}
        </section>

        {/* 6. 班级活跃率对比 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <BarChart3 className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">六、班级活跃率对比</h2>
          </div>
          {classComparison.length === 0 ? (
            <p className="text-sm text-gray-400">暂无班级数据</p>
          ) : classComparison.length === 1 ? (
            <p className="text-sm text-gray-500">仅管理一个班级</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-100 text-left text-gray-600">
                    <th className="px-3 py-2 font-medium">班级</th>
                    <th className="px-3 py-2 text-right font-medium">学生数</th>
                    <th className="px-3 py-2 text-right font-medium">今日活跃</th>
                    <th className="px-3 py-2 text-right font-medium">活跃率</th>
                  </tr>
                </thead>
                <tbody>
                  {classComparison.map((c) => (
                    <tr key={c.class_id} className="border-t border-gray-200">
                      <td className="px-3 py-1.5">{c.class_name}</td>
                      <td className="px-3 py-1.5 text-right">{c.total_students}</td>
                      <td className="px-3 py-1.5 text-right">{c.active_today}</td>
                      <td className="px-3 py-1.5 text-right">
                        {Math.round(c.active_rate * 100)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 7. 学生活跃度排行 TOP10 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <Trophy className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">七、学生活跃度排行 TOP10</h2>
          </div>
          {studentRanking.length === 0 ? (
            <p className="text-sm text-gray-400">暂无学生数据</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-100 text-left text-gray-600">
                    <th className="px-3 py-2 font-medium">排名</th>
                    <th className="px-3 py-2 font-medium">学号</th>
                    <th className="px-3 py-2 font-medium">姓名</th>
                    <th className="px-3 py-2 text-right font-medium">累计对话</th>
                    <th className="px-3 py-2 text-right font-medium">活跃天数</th>
                    <th className="px-3 py-2 font-medium">最后活跃</th>
                  </tr>
                </thead>
                <tbody>
                  {studentRanking.slice(0, 10).map((s, i) => (
                    <tr key={s.user_id} className="border-t border-gray-200">
                      <td className="px-3 py-1.5">{i + 1}</td>
                      <td className="px-3 py-1.5 text-gray-600">{s.username}</td>
                      <td className="px-3 py-1.5 font-medium">{s.name}</td>
                      <td className="px-3 py-1.5 text-right font-medium">{s.total_sessions}</td>
                      <td className="px-3 py-1.5 text-right">{s.active_days}</td>
                      <td className="px-3 py-1.5 text-gray-600">
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
        </section>

        {/* 8. 待关注学生 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="size-4 text-red-500" />
            <h2 className="text-base font-semibold text-gray-900">八、待关注学生</h2>
          </div>
          {anomalies.length === 0 ? (
            <p className="text-sm text-gray-400">所有学生状态良好</p>
          ) : (
            <div className="space-y-2">
              {anomalies.map((s) => (
                <div
                  key={s.user_id}
                  className="flex items-center justify-between rounded border border-red-200 bg-red-50 px-3 py-2 text-sm"
                >
                  <div>
                    <span className="font-medium">{s.name}</span>
                    <span className="ml-2 text-gray-600">
                      {s.class_name}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="font-medium text-red-600">
                      {s.inactive_days === 999 ? "从未登录" : `${s.inactive_days}天未登录`}
                    </span>
                    {s.last_active_at && (
                      <span className="ml-2 text-xs text-gray-500">
                        最后活跃：{new Date(s.last_active_at).toLocaleDateString("zh-CN").replace(/\//g, "-")}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 9. 重点学生 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-500" />
            <h2 className="text-base font-semibold text-gray-900">九、重点学生</h2>
          </div>
          {keyStudents.length === 0 ? (
            <p className="text-sm text-gray-400">暂无重点学生</p>
          ) : (
            <div className="space-y-2">
              {keyStudents.map((s) => (
                <div
                  key={s.user_id}
                  className={`flex items-center justify-between rounded border px-3 py-2 text-sm ${
                    s.level === "high_risk"
                      ? "border-red-200 bg-red-50"
                      : "border-amber-200 bg-amber-50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-xs text-white ${
                        s.level === "high_risk" ? "bg-red-500" : "bg-amber-500"
                      }`}
                    >
                      {s.level === "high_risk" ? "高风险" : "高优先级"}
                    </span>
                    <span className="font-medium">{s.name}</span>
                    <span className="text-gray-600">{s.class_name}</span>
                  </div>
                  <div className="text-right text-xs text-gray-600">
                    <div>{s.reason}</div>
                    <div>
                      会话 {s.session_count} 次 · AI回复 {s.assistant_messages} 轮
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-gray-400">
            【规则说明】高风险 = 窗口内有会话但 AI 从未回复；高优先级 = 长时间未活跃（待关注）。冷启动期 message 表暂无消息数据时自动跳过高风险判定，避免误报。
          </p>
        </section>

        {/* 10. 页脚 */}
        <footer className="border-t border-gray-200 pt-3 text-xs text-gray-400">
          <p>本报告为 P1 阶段版本（含互动明细、研究摘要、重点学生），会话级指标口径以学情总览页为准，消息级指标口径见互动明细注释。</p>
        </footer>
      </div>
    </div>
  );
}

// 报告页主体需在 Suspense 内使用 useSearchParams（Next.js 15 build 安全）
export default function ReportPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-muted-foreground">
          加载中...
        </div>
      }
    >
      <ReportPageInner />
    </Suspense>
  );
}

// 核心指标卡片
function StatCard({
  icon,
  label,
  value,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="flex items-center gap-1.5 text-xs text-gray-500">
        {icon}
        {label}
      </div>
      <div
        className={`mt-1 text-xl font-semibold ${
          highlight ? "text-red-600" : "text-gray-900"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

// 迷你统计
function MiniStat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 font-medium text-gray-900">{value}</div>
    </div>
  );
}
