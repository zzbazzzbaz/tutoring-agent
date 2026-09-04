// 班级管理-API 封装
import { api } from "./client";
import type {
  AddStudentsRequest,
  ClassInfo,
  ClassCreate,
  ClassUpdate,
  ClassSession,
  ClassStats,
  ClassStudent,
  Student,
  ImportResult,
  Page,
} from "@/lib/types";

function buildListQuery(
  teacher_id?: string,
  status?: string,
  keyword?: string,
  page = 1,
  pageSize = 20,
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (teacher_id) params.set("teacher_id", teacher_id);
  if (status) params.set("status", status);
  if (keyword) params.set("keyword", keyword);
  return params.toString();
}

export const classesApi = {
  list: (teacher_id?: string, status?: string, keyword?: string, page = 1, pageSize = 20) =>
    api.get<Page<ClassInfo>>(`/classes?${buildListQuery(teacher_id, status, keyword, page, pageSize)}`),

  get: (id: string) => api.get<ClassInfo>(`/classes/${id}`),

  create: (data: ClassCreate) => api.post<ClassInfo>("/classes", data),

  update: (id: string, data: ClassUpdate) =>
    api.patch<ClassInfo>(`/classes/${id}`, data),

  delete: (id: string) => api.delete<void>(`/classes/${id}`),

  addStudents: (classId: string, userIds: string[]) =>
    api.post<{ added: number }>(`/classes/${classId}/students`, { user_ids: userIds }),

  removeStudent: (classId: string, userId: string) =>
    api.delete<void>(`/classes/${classId}/students/${userId}`),

  bulkRemoveStudents: (classId: string, userIds: string[]) =>
    api.post<{ removed: number }>(`/classes/${classId}/students/bulk-remove`, { user_ids: userIds }),

  listStudents: (classId: string, keyword?: string, page = 1, pageSize = 20) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (keyword) params.set("keyword", keyword);
    return api.get<Page<ClassStudent>>(`/classes/${classId}/students?${params.toString()}`);
  },

  listSessions: (classId: string, mode?: string, keyword?: string, page = 1, pageSize = 20) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (mode) params.set("mode", mode);
    if (keyword) params.set("keyword", keyword);
    return api.get<Page<ClassSession>>(`/classes/${classId}/sessions?${params.toString()}`);
  },

  getStats: (classId: string) => api.get<ClassStats>(`/classes/${classId}/stats`),

  resetPassword: (classId: string, userId: string) =>
    api.post<void>(`/classes/${classId}/students/${userId}/reset-password`),

  listUnassignedStudents: (page = 1, pageSize = 100, keyword?: string) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (keyword) params.set("keyword", keyword);
    return api.get<Page<Student>>(`/classes/students/unassigned?${params.toString()}`);
  },

  importStudents: (classId: string, formData: FormData) =>
    api.postForm<ImportResult>(`/classes/${classId}/students/import`, formData),

  downloadTemplate: () => api.getBlob("/classes/students/template"),

  bulkDeleteStudents: (classId: string, userIds: string[], reason: string) =>
    api.post<{ deleted: number }>(`/classes/${classId}/students/bulk-delete`, {
      user_ids: userIds,
      reason,
    }),
};