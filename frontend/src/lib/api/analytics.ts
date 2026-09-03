//统计分析
import { api } from "./client";
import type {
  ClassEvaluationResponse,
  DashboardResponse,
  DashboardSummaryResponse,
  ProjectProgressResponse,
  StudentAnalysisResponse,
} from "@/lib/types";

export const analyticsApi = {
  // 获取学情总览数据
  getDashboard: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<DashboardResponse>(`/analytics/dashboard${qs ? `?${qs}` : ""}`);
  },
  // 获取 LLM 研究摘要（未配置 key/异常时后端返回 503）
  getDashboardSummary: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<DashboardSummaryResponse>(`/analytics/dashboard/summary${qs ? `?${qs}` : ""}`);
  },
  // 获取案例维度进度聚合（阶段分布/产出物完成；进度为跨会话累积的当前状态，不限时间窗口）
  getProjectProgress: (classId?: string) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    const qs = params.toString();
    return api.get<ProjectProgressResponse>(`/analytics/project-progress${qs ? `?${qs}` : ""}`);
  },
  // 获取班级评价（随 7/30 天窗口切换）
  getClassEvaluation: (classId?: string, days?: number) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    if (days) params.set("days", String(days));
    const qs = params.toString();
    return api.get<ClassEvaluationResponse>(`/analytics/class-evaluation${qs ? `?${qs}` : ""}`);
  },
  // 获取学生分析数据
  getStudentAnalysis: (userId: string, days = 30) => {
    return api.get<StudentAnalysisResponse>(`/analytics/students/${userId}?days=${days}`);
  },
};