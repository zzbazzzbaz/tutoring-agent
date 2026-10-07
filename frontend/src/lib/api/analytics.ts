//统计分析
import { api } from "./client";
import type {
  ClassEvaluationResponse,
  DashboardResponse,
  DashboardSummaryResponse,
  ProjectProgressResponse,
  ScoringPromptResponse,
  ScoringResultResponse,
  StudentAnalysisResponse,
} from "@/lib/types";

export const analyticsApi = {
  // 获取学情总览数据
  getDashboard: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<DashboardResponse>(
      `/analytics/dashboard${qs ? `?${qs}` : ""}`,
    );
  },
  // 获取 LLM 研究摘要（未配置 key/异常时后端返回 503）
  getDashboardSummary: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<DashboardSummaryResponse>(
      `/analytics/dashboard/summary${qs ? `?${qs}` : ""}`,
    );
  },
  // 获取案例维度进度聚合（阶段分布/产出物完成；进度为跨会话累积的当前状态，不限时间窗口）
  getProjectProgress: (classId?: string) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    const qs = params.toString();
    return api.get<ProjectProgressResponse>(
      `/analytics/project-progress${qs ? `?${qs}` : ""}`,
    );
  },
  // 获取班级评价（随 7/30 天窗口切换）
  getClassEvaluation: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<ClassEvaluationResponse>(
      `/analytics/class-evaluation${qs ? `?${qs}` : ""}`,
    );
  },
  // 获取学生分析数据
  getStudentAnalysis: (userId: string, days = 30) => {
    return api.get<StudentAnalysisResponse>(
      `/analytics/students/${userId}?days=${days}`,
    );
  },
  // 导出使用统计报告（Word 文档下载）
  exportReport: async (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    const blob = await api.getBlob(
      `/analytics/export-report${qs ? `?${qs}` : ""}`,
    );
    // 触发浏览器下载
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `使用统计报告_${new Date().toISOString().slice(0, 10)}.docx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  // 读取评分提示词（未自定义时返回系统默认模板）
  getScoringPrompt: () =>
    api.get<ScoringPromptResponse>("/analytics/scoring/prompt"),
  // 保存评分提示词
  saveScoringPrompt: (prompt: string) =>
    api.patch<ScoringPromptResponse>("/analytics/scoring/prompt", { prompt }),
  // 生成平时分（同步，可能 30-60s）
  generateScoring: (classId: string, since?: string) =>
    api.post<ScoringResultResponse>("/analytics/scoring/generate", {
      class_id: classId,
      since: since || null,
    }),
  // 读取班级最近一次平时分
  getScoring: (classId: string) =>
    api.get<ScoringResultResponse>(`/analytics/scoring?class_id=${classId}`),
  // 导出平时分成绩表（Word 下载）
  exportScoring: async (classId: string) => {
    const blob = await api.getBlob(
      `/analytics/scoring/export?class_id=${classId}`,
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `平时分成绩表_${new Date().toISOString().slice(0, 10)}.docx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
