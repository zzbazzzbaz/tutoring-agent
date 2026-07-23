import { api } from "./client";
import type { Student, ImportResult, Page, Session } from "@/lib/types";

function pageQuery(page = 1, pageSize = 20) {
  return `page=${page}&page_size=${pageSize}`;
}

export const usersApi = {
  listStudents: (page = 1, pageSize = 20) =>
    api.get<Page<Student>>(`/users/students?${pageQuery(page, pageSize)}`),

  listTeachers: () => api.get<Student[]>("/users/teachers"),

  delete: (userId: string) => api.delete<void>(`/users/${userId}`),

  resetPassword: (userId: string) =>
    api.post<void>(`/users/${userId}/reset-password`),

  getSessions: (userId: string, page = 1, pageSize = 20) =>
    api.get<Page<Session>>(
      `/users/${userId}/sessions?${pageQuery(page, pageSize)}`,
    ),

  import: (formData: FormData) =>
    api.postForm<ImportResult>("/users/students/import", formData),

  downloadTemplate: () => api.getBlob("/users/students/template"),

  uploadAvatar: (formData: FormData) =>
    api.postForm<{ avatar_url: string }>("/users/me/avatar", formData),
};
