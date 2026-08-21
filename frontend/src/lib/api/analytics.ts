//统计分析
import { api } from "./client";
import type { DashboardResponse, StudentAnalysisResponse  } from "@/lib/types";

export const analyticsApi = {
  // 获取学情总览数据
  getDashboard: (classId?: string) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    const qs = params.toString();
    return api.get<DashboardResponse>(`/analytics/dashboard${qs ? `?${qs}` : ""}`);
  },
  // 获取学生分析数据
  getStudentAnalysis: (userId: string) => {
    return api.get<StudentAnalysisResponse>(`/analytics/students/${userId}`);
  },
};