//统计分析
import { api } from "./client";
import type { DashboardResponse, DashboardSummaryResponse, StudentAnalysisResponse } from "@/lib/types";

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
  // 获取学生分析数据
  getStudentAnalysis: (userId: string, days = 30) => {
    return api.get<StudentAnalysisResponse>(`/analytics/students/${userId}?days=${days}`);
  },
};