export const STORAGE_KEYS = {
  TOKEN: "tutoring_token",
  USER: "tutoring_user",
} as const;

export const COOKIE_KEYS = {
  AUTH: "tutoring_auth",
  ROLE: "tutoring_role",
} as const;

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "/api";
export const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "/agent";
export const ASSISTANT_ID =
  process.env.NEXT_PUBLIC_ASSISTANT_ID ?? "tutor";

export const ROUTES = {
  LOGIN: "/login",
  STUDENT_CHAT: "/student/chat",
  STUDENT_PROJECTS: "/student/manage/projects",
  TEACHER_CHAT: "/teacher/chat",
  TEACHER_PROJECTS: "/teacher/manage/projects",
  TEACHER_STUDENTS: "/teacher/manage/students",
} as const;
