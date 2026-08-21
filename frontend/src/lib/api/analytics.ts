import { api } from "./client";
import type { DashboardResponse } from "@/lib/types";

export const analyticsApi = {
  getDashboard: (classId?: string) => {
    const params = new URLSearchParams();
    if (classId) params.set("class_id", classId);
    const qs = params.toString();
    return api.get<DashboardResponse>(`/analytics/dashboard${qs ? `?${qs}` : ""}`);
  },
};