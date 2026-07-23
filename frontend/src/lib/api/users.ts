import { api } from "./client";
import type { Student, ImportResult, Session } from "@/lib/types";

export const usersApi = {
  listStudents: () => api.get<Student[]>("/users/students"),

  listTeachers: () => api.get<Student[]>("/users/teachers"),

  delete: (userId: string) => api.delete<void>(`/users/${userId}`),

  resetPassword: (userId: string) =>
    api.post<void>(`/users/${userId}/reset-password`),

  getSessions: (userId: string) =>
    api.get<Session[]>(`/users/${userId}/sessions`),

  import: (formData: FormData) =>
    api.postForm<ImportResult>("/users/students/import", formData),

  downloadTemplate: () => api.getBlob("/users/students/template"),
};
