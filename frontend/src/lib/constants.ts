export const STORAGE_KEYS = {
  TOKEN: "tutoring_token",
  USER: "tutoring_user",
} as const;

export const COOKIE_KEYS = {
  AUTH: "tutoring_auth",
  ROLE: "tutoring_role",
} as const;

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://127.0.0.1:2024";
export const ASSISTANT_ID =
  process.env.NEXT_PUBLIC_ASSISTANT_ID ?? "tutor";

export const ROUTES = {
  LOGIN: "/login",
  STUDENT_CHAT: "/student/chat",
  STUDENT_PROJECTS: "/student/projects",
  TEACHER_CHAT: "/teacher/chat",
  TEACHER_PROJECTS: "/teacher/projects",
  TEACHER_STUDENTS: "/teacher/students",
} as const;
