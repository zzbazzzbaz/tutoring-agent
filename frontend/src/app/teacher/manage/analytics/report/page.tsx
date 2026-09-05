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
  GraduationCap,
  RefreshCw,
  TrendingUp,
  Trophy,
  Printer,
  BarChart3,
  MessageSquare,
  Bot,
  Repeat,
  Target,
  ListChecks,
  CheckCircle2,
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
  ClassComparison,
  ClassEvaluationDimension,
  ClassEvaluationItem,
  ClassEvaluationResponse,
  ClassInfo,
  DashboardOverview,
  KeyStudent,
  LearningTrendPoint,
  MessageStats,
  ProjectProgressResponse,
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
  const [trend, setTrend] = useState<LearningTrendPoint[]>([]);
  const [classComparison, setClassComparison] = useState<ClassComparison[]>([]);
  const [studentRanking, setStudentRanking] = useState<StudentRanking[]>([]);
  const [messageStats, setMessageStats] = useState<MessageStats | null>(null);
  const [keyStudents, setKeyStudents] = useState<KeyStudent[]>([]);
  const [projectProgress, setProjectProgress] = useState<ProjectProgressResponse | null>(null);
  const [classEvaluation, setClassEvaluation] = useState<ClassEvaluationResponse | null>(null);
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
      setTrend(data.trend || []);
      setClassComparison(data.class_comparison || []);
      setStudentRanking(data.student_ranking || []);
      setMessageStats(data.message_stats || null);
      setKeyStudents(data.key_students || []);
    } catch (err: any) {
      console.error("加载报告数据失败:", err);
      setError(err?.message || "加载失败，请重试");
      throw err;
    }
    // 案例维度进度聚合：进度为跨会话累积的当前状态，不限时间窗口（不随 days 切换），独立请求不拖累主报告
    try {
      const progress = await analyticsApi.getProjectProgress(classId);
      setProjectProgress(progress);
    } catch (err: any) {
      console.error("加载案例进度聚合失败:", err);
      setProjectProgress(null);
    }
    // 班级评价：随班级与 days 窗口切换
    try {
      const evaluation = await analyticsApi.getClassEvaluation(classId, d);
      setClassEvaluation(evaluation);
    } catch (err: any) {
      console.error("加载班级评价失败:", err);
      setClassEvaluation(null);
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
  // 日均对话 = 窗口内对话数（趋势序列求和）÷ 窗口天数；
  const windowSessions = trend.reduce((sum, t) => sum + t.session_count, 0);
  const dailyAvg = trend.length > 0 ? windowSessions / trend.length : 0;

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
      `统计窗口内对话 ${windowSessions} 次，日均 ${dailyAvg.toFixed(1)} 次；历史累计对话 ${overview!.total_sessions} 次。`
    );
    if (peak && peak.session_count > 0) {
      parts.push(
        `${activeDays} 天有学生互动，互动峰值出现在 ${peak.date}（${peak.session_count} 次）。`
      );
    } else {
      parts.push("统计窗口内暂无对话记录。");
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
          className="inline-flex items-center gap-2 rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          <Printer className="size-4" />
          导出 PDF
        </button>
      </div>

      {/* 报告正文：始终白底黑字，打印友好 */}
      <div className="mx-auto max-w-4xl space-y-6 bg-white p-6 text-gray-900 shadow-sm print:max-w-none print:space-y-5 print:p-0 print:shadow-none">
        {/* 1. 报告头 */}
        <header className="border-b-2 border-blue-700 pb-4">
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
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard icon={<Users className="size-4" />} label="学生总数" value={overview.total_students} />
            <StatCard icon={<Activity className="size-4" />} label="今日活跃" value={`${overview.active_today}/${overview.total_students}`} />
            <StatCard icon={<GraduationCap className="size-4" />} label="累计对话" value={`${overview.total_sessions} 次`} />
            <StatCard
              icon={<AlertTriangle className="size-4" />}
              label="待关注"
              value={overview.pending_alert_count}
              highlight={overview.pending_alert_count > 0}
            />
          </div>
        </section>

        {/* 3. 互动明细 :互动明细基于 message 表统计*/}
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
            【口径注释】短期内显示 0/暂无属正常冷启动。平均轮次 = AI 回复数 ÷ 窗口内产生过消息的会话数；知识命中率 = 命中知识库的学生提问 ÷ 学生提问总数。
          </p>
        </section>

        {/* 3. 阶段分布与产出物完成（案例维度聚合，进度为跨会话累积的当前状态,阶段状态取最高值（pending<进行中<已完成）） */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <ListChecks className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">三、阶段分布与产出物完成</h2>
          </div>
          {!projectProgress || projectProgress.projects.length === 0 ? (
            <p className="text-sm text-gray-400">暂无可展示的已发布案例</p>
          ) : (
            <div className="space-y-4">
              {projectProgress.projects.map((proj) => (
                <div key={proj.project_id} className="rounded-lg border border-gray-200">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-gray-100 bg-gray-50 px-3 py-2 text-sm">
                    <span className="font-semibold text-gray-900">{proj.project_name}</span>
                    <span className="text-gray-500">参与学生 {proj.student_count}</span>
                    <span className="text-gray-500">阶段数 {proj.stage_count}</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-100 text-left text-gray-600">
                          <th className="px-3 py-2 font-medium">阶段</th>
                          <th className="px-3 py-2 font-medium">产出物</th>
                          <th className="px-3 py-2 text-right font-medium">已完成</th>
                          <th className="px-3 py-2 text-right font-medium">进行中</th>
                          <th className="px-3 py-2 text-right font-medium">已开始</th>
                          <th className="px-3 py-2 text-right font-medium">产出物提交</th>
                          <th className="px-3 py-2 text-right font-medium">产出物达标</th>
                        </tr>
                      </thead>
                      <tbody>
                        {proj.stages.map((st) => (
                          <tr key={st.stage_id} className="border-t border-gray-200">
                            <td className="px-3 py-1.5 font-medium">{st.title}</td>
                            <td className="px-3 py-1.5 text-gray-600">
                              {st.has_deliverable ? st.deliverable_title || "—" : "—"}
                            </td>
                            <td className="px-3 py-1.5 text-right">{st.completed_count}</td>
                            <td className="px-3 py-1.5 text-right">{st.in_progress_count}</td>
                            <td className="px-3 py-1.5 text-right">{st.started_count}</td>
                            <td className="px-3 py-1.5 text-right">
                              {st.deliverable_submitted_count}
                            </td>
                            <td className="px-3 py-1.5 text-right">
                              <span className="inline-flex items-center gap-1 text-blue-700">
                                {st.deliverable_done_count > 0 && (
                                  <CheckCircle2 className="size-3.5" />
                                )}
                                {st.deliverable_done_count}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-gray-400">
            【口径注释】按案例维度聚合（学生×案例合并会话进度）：阶段状态取最高值，产出物"已达标优先"；进度为跨会话累积的当前状态，不限时间窗口，不随报告天数切换变化。
          </p>
        </section>

        {/* 4. 数据摘要 */}
        <section>
          <h2 className="mb-2 text-base font-semibold text-gray-900">四、数据摘要</h2>
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
              ）
            </p>
          )}
        </section>

        {/* 5. 趋势概览(若后端将该密集日序列改为稀疏数组，本均值将静默退化为「滚动 N 条」，需同步前端。) */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <TrendingUp className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">五、趋势概览</h2>
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
            【口径注释】三日滑动均值按自然日滑动计算：每个日期取「当天 + 前 2 天」窗口内对话数的平均，开头第 1/2 天按已有天数平均。
          </p>
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

        {/* 8. 学生活跃度排行 TOP10 */}
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

        {/* 8. 重点学生 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-500" />
            <h2 className="text-base font-semibold text-gray-900">八、重点学生</h2>
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
            【规则说明】高风险 = 窗口内有会话但 AI 从未回复；高优先级 = 长时间未活跃（待关注）。冷启动期暂无消息数据时自动跳过高风险判定，避免误报。
          </p>
        </section>

        {/* 11. 班级评价 */}
        <section>
          <div className="mb-2 flex items-center gap-2">
            <BarChart3 className="size-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">九、班级评价</h2>
          </div>
          {!classEvaluation || classEvaluation.classes.length === 0 ? (
            <p className="text-sm text-gray-400">暂无班级评价数据</p>
          ) : classEvaluation.classes.length === 1 ? (
            // 指定班级：单班六维卡片
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {classEvaluation.classes[0].dimensions.map((dim) => (
                <ClassEvaluationCard key={dim.dimension_id} dim={dim} />
              ))}
            </div>
          ) : (
            // 全部班级：班级×维度横向对比表（不做跨班混算）
            <ClassComparisonTable classes={classEvaluation.classes} />
          )}
          <p className="mt-2 space-y-1 text-xs leading-relaxed text-gray-400">
            <span className="block">
              【口径注释】六维：参与度 / 思考质量 / 知识运用 / 产出物完成 / 阶段覆盖 / 学科；选择「全部班级」时按班级逐一计算并横向对比（不做跨班混算）。等级统一：≥80 高 / 60-79 中 / &lt;60 低。
            </span>
            <span className="block">
              · 参与度 = 活跃率×40% + 会话强度×30% + 互动深度×30%；活跃率 = 窗口内有会话的学生 ÷ 学生总数；会话强度按人均 5 会话、互动深度按人均 30 条学生消息为满分（封顶 100）。
            </span>
            <span className="block">
              · 思考质量 = 提问深度×30% + 主动追问×25% + 知识命中率×25% + 多轮持续度×20%；提问深度 = 含深度词（为什么/如何/怎样/怎么/哪些/如果/是否/原因/机制/原理/影响/比较/区别/联系/分析/解释/结合/依据）的提问占比；主动追问 = 非会话首条学生消息占比；多轮持续度按人均 5 轮为满分（封顶 100）。
            </span>
            <span className="block">
              · 知识运用 = 命中知识库的学生提问 ÷ 学生提问总数 × 100。
            </span>
            <span className="block">
              · 产出物完成 = 提交率×50% + 达标率×50%；提交率 = 已提交条目 ÷（参与学生 × 有产出物阶段数），达标率 = 已达标条目 ÷ 已提交条目；按案例维度聚合（跨会话累积、不限时间窗口，与「三、阶段分布与产出物完成」一致）。
            </span>
            <span className="block">
              · 阶段覆盖 = 阶段完成率×70% + 阶段覆盖率×30%；完成率 = 已完成条目 ÷（参与学生 × 案例阶段总数），覆盖率 = 已开始条目 ÷（参与学生 × 案例阶段总数）；按案例维度聚合（跨会话累积、不限时间窗口，与「三、阶段分布与产出物完成」一致）。
            </span>
            <span className="block">
              · 学科 = 知识点覆盖×40% + 案例分析×30% + 情境应用×30%；知识点覆盖 = 学生人均命中去重文档数 ÷ 全班命中去重文档总数 × 100；案例分析 = 案例类产出物（标题含 记录/案例/观察/分析）达标条目 ÷ 已提交条目 × 100；情境应用 = 方案类产出物（标题含 方案/设计/计划/策略）达标条目 ÷ 已提交条目 × 100；按案例维度聚合（不限时间窗口），标题分类互斥（案例优先）。
            </span>
          </p>
        </section>
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

// 等级徽章（班级评价：高/中/低）
function LevelBadge({ level }: { level: string }) {
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs text-white ${
        level === "高" ? "bg-blue-600" : level === "中" ? "bg-amber-500" : "bg-red-500"
      }`}
    >
      {level}
    </span>
  );
}

// 班级评价：单班六维卡片
function ClassEvaluationCard({ dim }: { dim: ClassEvaluationDimension }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{dim.name}</span>
        <LevelBadge level={dim.level} />
      </div>
      <div className="mt-1 text-2xl font-bold text-gray-900">{dim.score}</div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
        {dim.metrics.map((m) => (
          <div key={m.label} className="flex items-baseline justify-between text-xs">
            <span className="text-gray-500">{m.label}</span>
            <span className="font-medium text-gray-700">{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// 班级评价：多班级 × 维度横向对比表（全部班级时展示，逐班独立计算，不做混算）
function ClassComparisonTable({ classes }: { classes: ClassEvaluationItem[] }) {
  // 维度行 = 各班维度并集（保持出现顺序；当前各班维度集合一致）
  const dimensionIds: string[] = [];
  const seen = new Set<string>();
  classes.forEach((c) =>
    c.dimensions.forEach((d) => {
      if (!seen.has(d.dimension_id)) {
        seen.add(d.dimension_id);
        dimensionIds.push(d.dimension_id);
      }
    })
  );
  const nameOf = (id: string) =>
    classes[0].dimensions.find((d) => d.dimension_id === id)?.name ?? id;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-500">
            <th className="px-3 py-2 font-medium">维度</th>
            {classes.map((c) => (
              <th key={c.class_id} className="px-3 py-2 font-medium">
                {c.class_name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dimensionIds.map((id) => (
            <tr key={id} className="border-b border-gray-100">
              <td className="px-3 py-2 text-gray-700">{nameOf(id)}</td>
              {classes.map((c) => {
                const dim = c.dimensions.find((d) => d.dimension_id === id);
                return (
                  <td key={c.class_id} className="px-3 py-2">
                    {dim ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="font-semibold text-gray-900">{dim.score}</span>
                        <LevelBadge level={dim.level} />
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
