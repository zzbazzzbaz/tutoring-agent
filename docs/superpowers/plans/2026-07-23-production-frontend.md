# Production Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production Next.js frontend with student/teacher role-based routing, reusing the chat module from `test_frontend/agent-chat-ui`.

**Architecture:** Single Next.js App Router app with role-prefixed routes (`/student/*`, `/teacher/*`). Dual clients: fetch-based API client for REST calls to API Server (:8000), @langchain/langgraph-sdk for streaming chat with Agent Server (:2024). Token in localStorage + flag cookies for middleware routing.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, @langchain/langgraph-sdk, nuqs, framer-motion, sonner, lucide-react.

## Global Constraints

- **Frontend directory:** `frontend/` at project root (`/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend`)
- **Source for migration:** `test_frontend/agent-chat-ui/`
- **API Server URL:** `http://127.0.0.1:8000` (env: `NEXT_PUBLIC_API_URL`)
- **Agent Server URL:** `http://127.0.0.1:2024` (env: `NEXT_PUBLIC_AGENT_URL`)
- **Assistant ID:** `tutor` (env: `NEXT_PUBLIC_ASSISTANT_ID`)
- **Seed users:** teacher1/teacher123, student1/student123, student2/student123
- **localStorage keys:** `tutoring_token` (token), `tutoring_user` (user JSON)
- **Cookie keys:** `tutoring_auth` (flag), `tutoring_role` (student|teacher)
- **SessionCreate schema:** `{ mode: "free" | "project", project_id?: UUID }` — no `title` field in API (title is nullable, set later or auto-generated)
- **SessionOut fields:** `id, user_id, mode, project_id, project_name, title, last_active_at, created_at`
- **ProjectOut fields:** `id, name, background_md, status, created_at, updated_at`
- **UserOut fields:** `id, username, role, name, created_at`
- **LoginResponse:** `{ token: string, user: { id, username, role, name } }`
- **ImportResult:** `{ total, created, skipped, errors: string[] }`
- **Error format:** `{ detail: { error: { code: string, message: string } } }`

---

## File Structure

```
frontend/
├── package.json
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json
├── .env
├── .env.local
├── eslint.config.ts
├── .prettierrc
├── src/
│   ├── app/
│   │   ├── layout.tsx                          # Root layout (Inter font, NuqsAdapter, AuthProvider, Toaster)
│   │   ├── globals.css                         # Copied from agent-chat-ui
│   │   ├── login/
│   │   │   └── page.tsx                        # Login page
│   │   ├── student/
│   │   │   ├── layout.tsx                      # Student layout (Sidebar + RoleGuard)
│   │   │   ├── chat/
│   │   │   │   └── page.tsx                    # Student chat page
│   │   │   └── projects/
│   │   │       ├── page.tsx                    # Student project list
│   │   │       └── [id]/
│   │   │           └── page.tsx                # Student project detail
│   │   └── teacher/
│   │       ├── layout.tsx                      # Teacher layout (Sidebar + RoleGuard)
│   │       ├── chat/
│   │       │   └── page.tsx                    # Teacher chat page
│   │       ├── projects/
│   │       │   ├── page.tsx                    # Teacher project management
│   │       │   └── [id]/
│   │       │       └── page.tsx                # Teacher project detail/edit
│   │       └── students/
│   │           ├── page.tsx                    # Student list + import
│   │           └── [id]/
│   │               ├── page.tsx                # Student detail (sessions)
│   │               └── sessions/
│   │                   └── [sid]/
│   │                       └── page.tsx        # Read-only conversation view
│   ├── components/
│   │   ├── ui/                                 # shadcn/ui (copied from agent-chat-ui)
│   │   ├── auth/
│   │   │   ├── AuthProvider.tsx                # Auth context
│   │   │   ├── LoginForm.tsx                   # Login form
│   │   │   └── RoleGuard.tsx                   # Role guard wrapper
│   │   ├── chat/
│   │   │   ├── StreamProvider.tsx              # Adapted from agent-chat-ui
│   │   │   ├── SessionProvider.tsx             # Replaces ThreadProvider
│   │   │   ├── ArtifactProvider.tsx            # Copied from agent-chat-ui
│   │   │   ├── ChatView.tsx                    # Shared chat view (3-column layout)
│   │   │   ├── NewSessionModal.tsx             # New session creation modal
│   │   │   ├── ReadOnlyChatView.tsx            # Read-only chat for teacher
│   │   │   ├── client.ts                       # LangGraph SDK client factory
│   │   │   └── thread/                         # Copied from agent-chat-ui components/thread/
│   │   │       ├── index.tsx
│   │   │       ├── artifact.tsx
│   │   │       ├── markdown-text.tsx
│   │   │       ├── markdown-styles.css
│   │   │       ├── syntax-highlighter.tsx
│   │   │       ├── tooltip-icon-button.tsx
│   │   │       ├── utils.ts
│   │   │       ├── ContentBlocksPreview.tsx
│   │   │       ├── MultimodalPreview.tsx
│   │   │       ├── agent-inbox/
│   │   │       ├── history/
│   │   │       └── messages/
│   │   ├── projects/
│   │   │   ├── ProjectList.tsx                 # List (read-only + CRUD modes)
│   │   │   ├── ProjectDetail.tsx               # Detail (read-only + edit modes)
│   │   │   └── ProjectFormModal.tsx            # Create/edit modal
│   │   ├── students/
│   │   │   ├── StudentTable.tsx                # Student list table
│   │   │   ├── StudentImportDialog.tsx         # Excel import
│   │   │   └── StudentSessionTable.tsx         # Student sessions table
│   │   └── layout/
│   │       └── AppSidebar.tsx                  # App navigation sidebar
│   ├── hooks/
│   │   ├── use-file-upload.tsx                 # Copied from agent-chat-ui
│   │   └── useMediaQuery.tsx                   # Copied from agent-chat-ui
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts                       # Base API client
│   │   │   ├── auth.ts                         # Auth API
│   │   │   ├── sessions.ts                     # Sessions API
│   │   │   ├── projects.ts                     # Projects API
│   │   │   └── users.ts                        # Users API
│   │   ├── types.ts                            # Shared TypeScript types
│   │   ├── utils.ts                            # Copied from agent-chat-ui (cn function)
│   │   ├── multimodal-utils.ts                 # Copied from agent-chat-ui
│   │   ├── agent-inbox-interrupt.ts            # Copied from agent-chat-ui
│   │   ├── ensure-tool-responses.ts            # Copied from agent-chat-ui
│   │   └── constants.ts                        # Constants
│   └── middleware.ts                           # Next.js middleware (route guard)
└── public/
    └── (icons, favicon, etc.)
```

---

### Task 1: Project Scaffold and Configuration

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/components.json`
- Create: `frontend/.env`
- Create: `frontend/.env.local`
- Create: `frontend/eslint.config.ts`
- Create: `frontend/.prettierrc`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/app/layout.tsx`

**Interfaces:**
- Produces: A runnable Next.js dev server at `localhost:3000`

- [ ] **Step 1: Create frontend directory and copy config files**

```bash
mkdir -p frontend/src/app
# Copy config files from agent-chat-ui
cp test_frontend/agent-chat-ui/next.config.ts frontend/
cp test_frontend/agent-chat-ui/tsconfig.json frontend/
cp test_frontend/agent-chat-ui/postcss.config.mjs frontend/
cp test_frontend/agent-chat-ui/eslint.config.ts frontend/
cp test_frontend/agent-chat-ui/.prettierrc frontend/
cp test_frontend/agent-chat-ui/components.json frontend/
```

- [ ] **Step 2: Create package.json**

Create `frontend/package.json` with the same dependencies as agent-chat-ui but renamed:

```json
{
  "name": "teaching-agent-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "lint:fix": "next lint --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  },
  "dependencies": {
    "@langchain/core": "^1.1.44",
    "@langchain/langgraph": "^1.4.8",
    "@langchain/langgraph-sdk": "^1.8.10",
    "@radix-ui/react-avatar": "^1.1.11",
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-dropdown-menu": "^2.1.15",
    "@radix-ui/react-label": "^2.1.8",
    "@radix-ui/react-select": "^2.2.5",
    "@radix-ui/react-separator": "^1.1.8",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-switch": "^1.2.6",
    "@radix-ui/react-table": "^1.1.5",
    "@radix-ui/react-tooltip": "^1.2.8",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "date-fns": "^4.1.0",
    "framer-motion": "^12.38.0",
    "katex": "^0.16.45",
    "lodash": "^4.18.1",
    "lucide-react": "^0.476.0",
    "next-themes": "^0.4.6",
    "nuqs": "^2.8.9",
    "react": "^19.2.5",
    "react-dom": "^19.2.5",
    "react-markdown": "^10.1.0",
    "react-syntax-highlighter": "^15.6.1",
    "recharts": "^2.15.3",
    "rehype-katex": "^7.0.1",
    "remark-gfm": "^4.0.1",
    "remark-math": "^6.0.0",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.5.0",
    "tailwindcss-animate": "^1.0.7",
    "use-stick-to-bottom": "^1.1.4",
    "uuid": "^14.0.1",
    "zod": "^4.4.2"
  },
  "devDependencies": {
    "@eslint/js": "^9.27.0",
    "@tailwindcss/postcss": "^4.2.4",
    "@types/lodash": "^4.17.24",
    "@types/node": "^22.15.18",
    "@types/react": "^19.2.14",
    "@types/react-dom": "^19.2.3",
    "@types/react-syntax-highlighter": "^15.5.13",
    "@types/uuid": "^10.0.0",
    "autoprefixer": "^10.5.0",
    "eslint": "^9.39.3",
    "eslint-config-next": "16.2.4",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.5.2",
    "globals": "^17.6.0",
    "next": "^15.5.18",
    "postcss": "^8.5.13",
    "prettier": "^3.8.3",
    "prettier-plugin-tailwindcss": "^0.8.0",
    "tailwind-scrollbar": "^4.0.2",
    "tailwindcss": "^4.2.4",
    "typescript": "~5.8.3",
    "typescript-eslint": "^8.59.1"
  },
  "overrides": {
    "react-is": "^19.0.0-rc-69d4b800-20241021"
  }
}
```

Note: Added `@radix-ui/react-dropdown-menu`, `@radix-ui/react-select`, `@radix-ui/react-table` for new UI components (tables, dropdowns, selects).

- [ ] **Step 3: Create .env files**

Create `frontend/.env`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_AGENT_URL=http://127.0.0.1:2024
NEXT_PUBLIC_ASSISTANT_ID=tutor
```

- [ ] **Step 4: Copy globals.css**

```bash
cp test_frontend/agent-chat-ui/src/app/globals.css frontend/src/app/globals.css
```

- [ ] **Step 5: Copy UI components and lib utilities from agent-chat-ui**

```bash
# Copy shadcn/ui components
cp -r test_frontend/agent-chat-ui/src/components/ui frontend/src/components/ui
# Copy icons
cp -r test_frontend/agent-chat-ui/src/components/icons frontend/src/components/icons
# Copy hooks
cp -r test_frontend/agent-chat-ui/src/hooks frontend/src/hooks
# Copy lib utilities
cp test_frontend/agent-chat-ui/src/lib/utils.ts frontend/src/lib/utils.ts
cp test_frontend/agent-chat-ui/src/lib/multimodal-utils.ts frontend/src/lib/multimodal-utils.ts
cp test_frontend/agent-chat-ui/src/lib/agent-inbox-interrupt.ts frontend/src/lib/agent-inbox-interrupt.ts
cp test_frontend/agent-chat-ui/src/lib/ensure-tool-responses.ts frontend/src/lib/ensure-tool-responses.ts
```

- [ ] **Step 6: Create root layout.tsx**

Create `frontend/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Inter } from "next/font/google";
import React from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({
  subsets: ["latin"],
  preload: true,
  display: "swap",
});

export const metadata: Metadata = {
  title: "教学 Agent",
  description: "智能教学助手平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <NuqsAdapter>
          <AuthProvider>
            {children}
            <Toaster />
          </AuthProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Install dependencies**

```bash
cd frontend && npm install
```

- [ ] **Step 8: Add shadcn/ui components needed for new features**

```bash
cd frontend
npx shadcn@latest add table select dropdown-menu badge
```

- [ ] **Step 9: Create placeholder home page to verify dev server**

Create `frontend/src/app/page.tsx`:

```tsx
export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <h1 className="text-2xl font-bold">教学 Agent</h1>
    </div>
  );
}
```

- [ ] **Step 10: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Server starts at `localhost:3000`, page shows "教学 Agent".

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend project with Next.js + shadcn/ui

Copy base config, UI components, and utilities from agent-chat-ui.
Add new Radix dependencies for table/select/dropdown components."
```

---

### Task 2: Types and API Client Layer

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/constants.ts`
- Create: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/auth.ts`
- Create: `frontend/src/lib/api/sessions.ts`
- Create: `frontend/src/lib/api/projects.ts`
- Create: `frontend/src/lib/api/users.ts`

**Interfaces:**
- Produces: `ApiClient` class with `get/post/patch/delete` methods
- Produces: Type definitions matching API Server schemas
- Produces: API module functions for auth, sessions, projects, users

- [ ] **Step 1: Create types.ts**

Create `frontend/src/lib/types.ts`:

```typescript
export type UserRole = "student" | "teacher";

export interface User {
  id: string;
  username: string;
  role: UserRole;
  name: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export type SessionMode = "free" | "project";

export interface Session {
  id: string;
  user_id: string;
  mode: SessionMode;
  project_id: string | null;
  project_name: string | null;
  title: string | null;
  last_active_at: string;
  created_at: string;
}

export interface SessionCreate {
  mode: SessionMode;
  project_id?: string;
}

export type ProjectStatus = "draft" | "published";

export interface Project {
  id: string;
  name: string;
  background_md: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  background_md: string;
  status: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  background_md?: string;
  status?: ProjectStatus;
}

export interface Student {
  id: string;
  username: string;
  role: string;
  name: string;
  created_at: string;
}

export interface ImportResult {
  total: number;
  created: number;
  skipped: number;
  errors: string[];
}
```

- [ ] **Step 2: Create constants.ts**

Create `frontend/src/lib/constants.ts`:

```typescript
export const STORAGE_KEYS = {
  TOKEN: "tutoring_token",
  USER: "tutoring_user",
} as const;

export const COOKIE_KEYS = {
  AUTH: "tutoring_auth",
  ROLE: "tutoring_role",
} as const;

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://127.0.0.1:2024";
export const ASSISTANT_ID = process.env.NEXT_PUBLIC_ASSISTANT_ID ?? "tutor";

export const ROUTES = {
  LOGIN: "/login",
  STUDENT_CHAT: "/student/chat",
  STUDENT_PROJECTS: "/student/projects",
  TEACHER_CHAT: "/teacher/chat",
  TEACHER_PROJECTS: "/teacher/projects",
  TEACHER_STUDENTS: "/teacher/students",
} as const;
```

- [ ] **Step 3: Create API client**

Create `frontend/src/lib/api/client.ts`:

```typescript
import { STORAGE_KEYS, COOKIE_KEYS, API_URL } from "@/lib/constants";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.TOKEN);
}

function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
  document.cookie = `${COOKIE_KEYS.AUTH}=; path=/; max-age=0`;
  document.cookie = `${COOKIE_KEYS.ROLE}=; path=/; max-age=0`;
  window.location.href = "/login";
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearAuth();
    throw new ApiError("UNAUTHORIZED", "登录已过期，请重新登录", 401);
  }

  if (!res.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `请求失败 (${res.status})`;
    try {
      const body = await res.json();
      const error = body?.detail?.error;
      if (error) {
        code = error.code ?? code;
        message = error.message ?? message;
      }
    } catch {
      // response body is not JSON
    }
    throw new ApiError(code, message, res.status);
  }

  // Handle blob responses (file downloads)
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return res.blob() as unknown as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
  postForm: <T>(path: string, formData: FormData) =>
    apiFetch<T>(path, {
      method: "POST",
      body: formData,
      headers: {},
    }),
  getBlob: (path: string) =>
    apiFetch<Blob>(path, { method: "GET" }),
};
```

- [ ] **Step 4: Create auth API**

Create `frontend/src/lib/api/auth.ts`:

```typescript
import { api } from "./client";
import type { LoginResponse, User } from "@/lib/types";

export const authApi = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { username, password }),

  logout: () => api.post<void>("/auth/logout"),

  me: () => api.get<User>("/auth/me"),

  changePassword: (oldPassword: string, newPassword: string) =>
    api.post<void>("/auth/change-password", {
      old_password: oldPassword,
      new_password: newPassword,
    }),
};
```

- [ ] **Step 5: Create sessions API**

Create `frontend/src/lib/api/sessions.ts`:

```typescript
import { api } from "./client";
import type { Session, SessionCreate } from "@/lib/types";

export const sessionsApi = {
  list: () => api.get<Session[]>("/sessions"),

  create: (data: SessionCreate) => api.post<Session>("/sessions", data),

  get: (id: string) => api.get<Session>(`/sessions/${id}`),

  delete: (id: string) => api.delete<void>(`/sessions/${id}`),

  listByUser: (userId: string) =>
    api.get<Session[]>(`/users/${userId}/sessions`),
};
```

- [ ] **Step 6: Create projects API**

Create `frontend/src/lib/api/projects.ts`:

```typescript
import { api } from "./client";
import type { Project, ProjectCreate, ProjectUpdate } from "@/lib/types";

export const projectsApi = {
  list: (status?: string) =>
    api.get<Project[]>(`/projects${status ? `?status=${status}` : ""}`),

  get: (id: string) => api.get<Project>(`/projects/${id}`),

  create: (data: ProjectCreate) => api.post<Project>("/projects", data),

  update: (id: string, data: ProjectUpdate) =>
    api.patch<Project>(`/projects/${id}`, data),

  delete: (id: string) => api.delete<void>(`/projects/${id}`),
};
```

- [ ] **Step 7: Create users API**

Create `frontend/src/lib/api/users.ts`:

```typescript
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
```

- [ ] **Step 8: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/
git commit -m "feat: add API client layer with typed wrappers for all endpoints

- ApiClient with Bearer token injection and auto-logout on 401
- Type definitions matching API Server schemas
- Module wrappers: auth, sessions, projects, users"
```

---

### Task 3: Authentication (AuthProvider + LoginForm + Login Page)

**Files:**
- Create: `frontend/src/components/auth/AuthProvider.tsx`
- Create: `frontend/src/components/auth/LoginForm.tsx`
- Create: `frontend/src/components/auth/RoleGuard.tsx`
- Create: `frontend/src/app/login/page.tsx`

**Interfaces:**
- Consumes: `authApi` from Task 2
- Produces: `useAuth()` hook returning `{ token, user, isAuthenticated, login, logout }`
- Produces: `RoleGuard` component accepting `{ role: UserRole }`

- [ ] **Step 1: Create AuthProvider**

Create `frontend/src/components/auth/AuthProvider.tsx`:

```tsx
"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { authApi } from "@/lib/api/auth";
import { STORAGE_KEYS, COOKIE_KEYS, ROUTES } from "@/lib/constants";
import type { User, UserRole } from "@/lib/types";

interface AuthContextValue {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${60 * 60 * 24 * 7}`;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore network errors on logout
    }
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    clearCookie(COOKIE_KEYS.AUTH);
    clearCookie(COOKIE_KEYS.ROLE);
    setToken(null);
    setUser(null);
    window.location.href = ROUTES.LOGIN;
  }, []);

  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_KEYS.TOKEN);
    const storedUser = localStorage.getItem(STORAGE_KEYS.USER);

    if (!storedToken || !storedUser) {
      setLoading(false);
      return;
    }

    setToken(storedToken);
    setUser(JSON.parse(storedUser));

    // Verify token validity
    authApi
      .me()
      .then((freshUser) => {
        setUser(freshUser);
        localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(freshUser));
      })
      .catch(() => {
        // Token is invalid
        localStorage.removeItem(STORAGE_KEYS.TOKEN);
        localStorage.removeItem(STORAGE_KEYS.USER);
        clearCookie(COOKIE_KEYS.AUTH);
        clearCookie(COOKIE_KEYS.ROLE);
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authApi.login(username, password);
    localStorage.setItem(STORAGE_KEYS.TOKEN, res.token);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(res.user));
    setCookie(COOKIE_KEYS.AUTH, "1");
    setCookie(COOKIE_KEYS.ROLE, res.user.role);
    setToken(res.token);
    setUser(res.user);

    // Redirect by role
    const role = res.user.role as UserRole;
    window.location.href =
      role === "teacher" ? ROUTES.TEACHER_CHAT : ROUTES.STUDENT_CHAT;
  }, []);

  return (
    <AuthContext.Provider
      value={{ token, user, isAuthenticated: !!token, loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Create LoginForm**

Create `frontend/src/components/auth/LoginForm.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useAuth } from "./AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export function LoginForm() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "登录失败，请重试";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 p-4">
      <div className="w-full max-w-sm rounded-lg border bg-background p-8 shadow-lg">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold tracking-tight">教学 Agent</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            请登录以继续使用
          </p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="username">用户名</Label>
            <Input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              placeholder="请输入用户名"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="请输入密码"
            />
          </div>
          <Button type="submit" disabled={loading} className="mt-2">
            {loading ? "登录中..." : "登录"}
          </Button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create login page**

Create `frontend/src/app/login/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { LoginForm } from "@/components/auth/LoginForm";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROUTES } from "@/lib/constants";

export default function LoginPage() {
  const { isAuthenticated, user, loading } = useAuth();

  useEffect(() => {
    if (!loading && isAuthenticated && user) {
      window.location.href =
        user.role === "teacher" ? ROUTES.TEACHER_CHAT : ROUTES.STUDENT_CHAT;
    }
  }, [loading, isAuthenticated, user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  return <LoginForm />;
}
```

- [ ] **Step 4: Create RoleGuard**

Create `frontend/src/components/auth/RoleGuard.tsx`:

```tsx
"use client";

import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { ROUTES } from "@/lib/constants";
import type { UserRole } from "@/lib/types";

export function RoleGuard({
  role,
  children,
}: {
  role: UserRole;
  children: ReactNode;
}) {
  const { user, loading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      window.location.href = ROUTES.LOGIN;
      return;
    }
    if (user && user.role !== role) {
      window.location.href =
        user.role === "teacher" ? ROUTES.TEACHER_CHAT : ROUTES.STUDENT_CHAT;
    }
  }, [user, role, loading, isAuthenticated]);

  if (loading || !isAuthenticated || (user && user.role !== role)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  return <>{children}</>;
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/auth/ frontend/src/app/login/
git commit -m "feat: add authentication with AuthProvider, LoginForm, and RoleGuard

- AuthProvider manages token in localStorage + flag cookies
- Auto-verifies token on mount via GET /auth/me
- LoginForm with username/password
- RoleGuard for role-based layout protection"
```

---

### Task 4: Middleware and Layouts

**Files:**
- Create: `frontend/src/middleware.ts`
- Create: `frontend/src/components/layout/AppSidebar.tsx`
- Create: `frontend/src/app/student/layout.tsx`
- Create: `frontend/src/app/teacher/layout.tsx`
- Delete: `frontend/src/app/page.tsx` (replace with redirect)

**Interfaces:**
- Consumes: `useAuth()` from Task 3, `RoleGuard` from Task 3
- Produces: `AppSidebar` component accepting `{ role: UserRole }`
- Produces: Student and teacher layout wrappers

- [ ] **Step 1: Create middleware.ts**

Create `frontend/src/middleware.ts`:

```typescript
import { NextResponse, type NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page access
  if (pathname === "/login") {
    // If already authenticated, redirect to role home
    const authCookie = request.cookies.get("tutoring_auth")?.value;
    const roleCookie = request.cookies.get("tutoring_role")?.value;
    if (authCookie === "1" && roleCookie) {
      const home = roleCookie === "teacher" ? "/teacher/chat" : "/student/chat";
      return NextResponse.redirect(new URL(home, request.url));
    }
    return NextResponse.next();
  }

  // Check authentication for all other routes
  const authCookie = request.cookies.get("tutoring_auth")?.value;
  const roleCookie = request.cookies.get("tutoring_role")?.value;

  if (authCookie !== "1") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Role-based route protection
  if (pathname.startsWith("/student") && roleCookie !== "student") {
    return NextResponse.redirect(new URL("/teacher/chat", request.url));
  }
  if (pathname.startsWith("/teacher") && roleCookie !== "teacher") {
    return NextResponse.redirect(new URL("/student/chat", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 2: Create AppSidebar**

Create `frontend/src/components/layout/AppSidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, FolderOpen, Users, LogOut } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { UserRole } from "@/lib/types";

interface NavItem {
  label: string;
  href: string;
  icon: typeof MessageSquare;
}

const STUDENT_NAV: NavItem[] = [
  { label: "对话", href: "/student/chat", icon: MessageSquare },
  { label: "项目", href: "/student/projects", icon: FolderOpen },
];

const TEACHER_NAV: NavItem[] = [
  { label: "对话", href: "/teacher/chat", icon: MessageSquare },
  { label: "项目", href: "/teacher/projects", icon: FolderOpen },
  { label: "学生", href: "/teacher/students", icon: Users },
];

export function AppSidebar({ role }: { role: UserRole }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const navItems = role === "teacher" ? TEACHER_NAV : STUDENT_NAV;

  return (
    <aside className="flex h-screen w-60 flex-col border-r bg-background">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-lg font-bold">教学 Agent</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3">
        <div className="mb-2 px-2 text-sm">
          <p className="font-medium">{user?.name}</p>
          <p className="text-xs text-muted-foreground">{user?.username}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={logout}
          className="w-full justify-start"
        >
          <LogOut className="mr-2 size-4" />
          退出登录
        </Button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Create student layout**

Create `frontend/src/app/student/layout.tsx`:

```tsx
"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppSidebar } from "@/components/layout/AppSidebar";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="student">
      <div className="flex h-screen">
        <AppSidebar role="student" />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </RoleGuard>
  );
}
```

- [ ] **Step 4: Create teacher layout**

Create `frontend/src/app/teacher/layout.tsx`:

```tsx
"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppSidebar } from "@/components/layout/AppSidebar";

export default function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="teacher">
      <div className="flex h-screen">
        <AppSidebar role="teacher" />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </RoleGuard>
  );
}
```

- [ ] **Step 5: Replace root page with redirect**

Delete `frontend/src/app/page.tsx` and create a new one:

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/login");
}
```

- [ ] **Step 6: Create placeholder pages for all routes**

Create these placeholder pages so the app compiles and navigation works:

`frontend/src/app/student/chat/page.tsx`:
```tsx
export default function StudentChatPage() {
  return <div className="p-4">学生对话页（待实现）</div>;
}
```

`frontend/src/app/student/projects/page.tsx`:
```tsx
export default function StudentProjectsPage() {
  return <div className="p-4">学生项目页（待实现）</div>;
}
```

`frontend/src/app/student/projects/[id]/page.tsx`:
```tsx
export default function StudentProjectDetailPage() {
  return <div className="p-4">项目详情（待实现）</div>;
}
```

`frontend/src/app/teacher/chat/page.tsx`:
```tsx
export default function TeacherChatPage() {
  return <div className="p-4">教师对话页（待实现）</div>;
}
```

`frontend/src/app/teacher/projects/page.tsx`:
```tsx
export default function TeacherProjectsPage() {
  return <div className="p-4">教师项目管理（待实现）</div>;
}
```

`frontend/src/app/teacher/projects/[id]/page.tsx`:
```tsx
export default function TeacherProjectDetailPage() {
  return <div className="p-4">项目详情（待实现）</div>;
}
```

`frontend/src/app/teacher/students/page.tsx`:
```tsx
export default function TeacherStudentsPage() {
  return <div className="p-4">学生管理（待实现）</div>;
}
```

`frontend/src/app/teacher/students/[id]/page.tsx`:
```tsx
export default function StudentDetailPage() {
  return <div className="p-4">学生详情（待实现）</div>;
}
```

`frontend/src/app/teacher/students/[id]/sessions/[sid]/page.tsx`:
```tsx
export default function StudentSessionViewPage() {
  return <div className="p-4">查看对话（待实现）</div>;
}
```

- [ ] **Step 7: Verify dev server and route guards**

```bash
cd frontend && npm run dev
```

Test in browser:
1. Visit `localhost:3000` -> should redirect to `/login`
2. Login as student1/student123 -> should redirect to `/student/chat`
3. Manually visit `/teacher/students` -> should redirect to `/student/chat`
4. Login as teacher1/teacher123 -> should redirect to `/teacher/chat`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/middleware.ts frontend/src/components/layout/ frontend/src/app/student/ frontend/src/app/teacher/ frontend/src/app/page.tsx
git commit -m "feat: add middleware route guards, app sidebar, and role layouts

- middleware.ts: cookie-based auth check + role-based routing
- AppSidebar: role-specific navigation
- Student/Teacher layouts with RoleGuard
- Placeholder pages for all routes"
```

---

### Task 5: Chat Module Migration (SessionProvider + StreamProvider + ChatView)

**Files:**
- Create: `frontend/src/components/chat/client.ts`
- Create: `frontend/src/components/chat/SessionProvider.tsx`
- Create: `frontend/src/components/chat/StreamProvider.tsx`
- Create: `frontend/src/components/chat/ArtifactProvider.tsx`
- Copy: `frontend/src/components/chat/thread/` (from agent-chat-ui)
- Create: `frontend/src/components/chat/ChatView.tsx`
- Create: `frontend/src/components/chat/NewSessionModal.tsx`

**Interfaces:**
- Consumes: `useAuth()` from Task 3, `sessionsApi` from Task 2, `projectsApi` from Task 2
- Produces: `SessionProvider` with `useSessions()` hook
- Produces: `StreamProvider` with `useStreamContext()` hook
- Produces: `ChatView` component (full 3-column chat layout)
- Produces: `NewSessionModal` component

- [ ] **Step 1: Copy thread components from agent-chat-ui**

```bash
mkdir -p frontend/src/components/chat
cp -r test_frontend/agent-chat-ui/src/components/thread frontend/src/components/chat/thread
cp test_frontend/agent-chat-ui/src/components/thread/artifact.tsx frontend/src/components/chat/ArtifactProvider.tsx
```

Note: `artifact.tsx` exports `ArtifactProvider` — rename the file but keep the export names. The internal imports in thread components use `@/` alias which will work as-is.

- [ ] **Step 2: Create adapted client.ts**

Create `frontend/src/components/chat/client.ts`:

```typescript
import { Client } from "@langchain/langgraph-sdk";
import { AGENT_URL } from "@/lib/constants";

export function createClient(authToken: string | undefined) {
  const defaultHeaders: Record<string, string> = {};
  if (authToken) {
    defaultHeaders["Authorization"] = `Bearer ${authToken}`;
  }
  return new Client({
    apiUrl: AGENT_URL,
    ...(Object.keys(defaultHeaders).length
      ? { defaultHeaders }
      : {}),
  });
}
```

- [ ] **Step 3: Create SessionProvider**

Create `frontend/src/components/chat/SessionProvider.tsx`:

```tsx
"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { sessionsApi } from "@/lib/api/sessions";
import type { Session } from "@/lib/types";

interface SessionContextValue {
  sessions: Session[];
  sessionsLoading: boolean;
  refreshSessions: () => Promise<void>;
  createSession: (mode: "free" | "project", projectId?: string) => Promise<Session>;
  deleteSession: (id: string) => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await sessionsApi.list();
      setSessions(data);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const createSession = useCallback(
    async (mode: "free" | "project", projectId?: string) => {
      const session = await sessionsApi.create({
        mode,
        project_id: projectId,
      });
      setSessions((prev) => [session, ...prev]);
      return session;
    },
    [],
  );

  const deleteSession = useCallback(async (id: string) => {
    await sessionsApi.delete(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return (
    <SessionContext.Provider
      value={{
        sessions,
        sessionsLoading,
        refreshSessions,
        createSession,
        deleteSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSessions() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSessions must be used within SessionProvider");
  return ctx;
}
```

- [ ] **Step 4: Create adapted StreamProvider**

Create `frontend/src/components/chat/StreamProvider.tsx`:

```tsx
"use client";

import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { useAuth } from "@/components/auth/AuthProvider";
import { useSessions } from "./SessionProvider";
import { AGENT_URL, ASSISTANT_ID } from "@/lib/constants";
import { toast } from "sonner";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function checkGraphStatus(
  apiUrl: string,
  authToken?: string,
): Promise<boolean> {
  try {
    const headers: HeadersInit = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    const res = await fetch(`${apiUrl}/info`, { headers });
    return res.ok;
  } catch (e) {
    console.error(e);
    return false;
  }
}

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function StreamProvider({
  children,
  readOnly = false,
}: {
  children: ReactNode;
  readOnly?: boolean;
}) {
  const { token } = useAuth();
  const { refreshSessions } = useSessions();
  const [threadId, setThreadId] = useQueryState("session");

  const streamValue = useTypedStream({
    apiUrl: AGENT_URL,
    assistantId: ASSISTANT_ID,
    defaultHeaders: token
      ? { Authorization: `Bearer ${token}` }
      : {},
    threadId: threadId ?? null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      if (!readOnly) {
        sleep()
          .then(() => refreshSessions())
          .catch(console.error);
      }
    },
  });

  useEffect(() => {
    if (token) {
      checkGraphStatus(AGENT_URL, token).then((ok) => {
        if (!ok) {
          toast.error("无法连接到 Agent 服务器", {
            description: `请确保 Agent Server 运行在 ${AGENT_URL}`,
            duration: 10000,
            richColors: true,
            closeButton: true,
          });
        }
      });
    }
  }, [token]);

  return (
    <StreamContext.Provider value={streamValue}>
      {children}
    </StreamContext.Provider>
  );
}

export function useStreamContext(): StreamContextType {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
}

export default StreamContext;
```

- [ ] **Step 5: Adapt thread/index.tsx**

The main Thread component from agent-chat-ui needs adaptation. It currently imports from `@/providers/Thread` and `@/providers/Stream`. Update these imports:

In `frontend/src/components/chat/thread/index.tsx`, find and replace:
- `from "@/providers/Stream"` -> `from "@/components/chat/StreamProvider"` 
- `from "./Thread"` or `from "@/providers/Thread"` -> `from "@/components/chat/SessionProvider"`
- `from "@/components/thread/artifact"` -> `from "@/components/chat/ArtifactProvider"`
- `from "@/components/thread/..."` -> `from "@/components/chat/thread/..."`

Also replace `useThreads()` with `useSessions()` and adapt the thread list rendering to use Session type instead of Thread type. The key changes:
- Thread list items show `session.title || (session.mode === 'free' ? '自由学习' : session.project_name || '项目模式')` instead of thread metadata
- Time display uses `session.last_active_at` or `session.created_at`
- Thread switching uses `setThreadId(session.id)` instead of `setThreadId(thread.thread_id)`

- [ ] **Step 6: Fix all imports in copied thread components**

Search through `frontend/src/components/chat/thread/` for any imports referencing `@/providers/` or `@/components/thread/` and update them to use `@/components/chat/thread/` or `@/components/chat/`.

```bash
# Find all files with old imports
grep -r "@/providers/" frontend/src/components/chat/thread/ || true
grep -r "@/components/thread/" frontend/src/components/chat/thread/ || true
```

Fix each file to use the new paths. Key files to check:
- `thread/index.tsx` - main component
- `thread/history/` - thread history sidebar
- `thread/messages/` - message components
- `thread/artifact.tsx` - artifact component

- [ ] **Step 7: Create NewSessionModal**

Create `frontend/src/components/chat/NewSessionModal.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useSessions } from "./SessionProvider";
import { projectsApi } from "@/lib/api/projects";
import type { Project } from "@/lib/types";
import { toast } from "sonner";

export function NewSessionModal({
  open,
  onClose,
  onCreated,
  preselectProjectId,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (sessionId: string) => void;
  preselectProjectId?: string;
}) {
  const { createSession } = useSessions();
  const [mode, setMode] = useState<"free" | "project">("free");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && preselectProjectId) {
      setMode("project");
      setSelectedProject(preselectProjectId);
    }
  }, [open, preselectProjectId]);

  useEffect(() => {
    if (open && mode === "project") {
      projectsApi.list("published").then(setProjects).catch(console.error);
    }
  }, [open, mode]);

  async function handleCreate() {
    if (mode === "project" && !selectedProject) {
      toast.error("请选择一个项目");
      return;
    }
    setLoading(true);
    try {
      const session = await createSession(mode, mode === "project" ? selectedProject : undefined);
      onCreated(session.id);
      onClose();
      // Reset form
      setMode("free");
      setSelectedProject("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建会话失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建会话</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Label>模式选择</Label>
            <RadioGroup
              value={mode}
              onValueChange={(v) => setMode(v as "free" | "project")}
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="free" id="free" />
                <Label htmlFor="free">自由学习模式</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="project" id="project" />
                <Label htmlFor="project">项目模式</Label>
              </div>
            </RadioGroup>
          </div>
          {mode === "project" && (
            <div className="flex flex-col gap-2">
              <Label>选择项目</Label>
              <Select value={selectedProject} onValueChange={setSelectedProject}>
                <SelectTrigger>
                  <SelectValue placeholder="请选择项目" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleCreate} disabled={loading}>
            {loading ? "创建中..." : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

Note: This component requires `radio-group` shadcn/ui component. Add it:

```bash
cd frontend && npx shadcn@latest add radio-group
```

- [ ] **Step 8: Create ChatView component**

Create `frontend/src/components/chat/ChatView.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { useQueryState } from "nuqs";
import { StreamProvider } from "./StreamProvider";
import { SessionProvider } from "./SessionProvider";
import { ArtifactProvider } from "./ArtifactProvider";
import { Thread } from "./thread";
import { NewSessionModal } from "./NewSessionModal";
import { useSessions } from "./SessionProvider";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Plus, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";

export function ChatView({
  role,
  readOnly = false,
  readOnlySessionId,
}: {
  role: "student" | "teacher";
  readOnly?: boolean;
  readOnlySessionId?: string;
}) {
  if (readOnly && readOnlySessionId) {
    return (
      <SessionProvider>
        <StreamProvider readOnly>
          <ArtifactProvider>
            <ReadOnlyChatContent sessionId={readOnlySessionId} />
          </ArtifactProvider>
        </StreamProvider>
      </SessionProvider>
    );
  }

  return (
    <SessionProvider>
      <StreamProvider>
        <ArtifactProvider>
          <ChatContent role={role} />
        </ArtifactProvider>
      </StreamProvider>
    </SessionProvider>
  );
}

function ChatContent({ role }: { role: "student" | "teacher" }) {
  const { sessions, sessionsLoading, refreshSessions, deleteSession } = useSessions();
  const [sessionId, setSessionId] = useQueryState("session");
  const [modalOpen, setModalOpen] = useState(false);
  const [projectPreselect, setProjectPreselect] = useState<string | undefined>();

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // Handle ?project=ID query param to pre-select project in new session modal
  const [projectParam, setProjectParam] = useQueryState("project");
  useEffect(() => {
    if (projectParam) {
      setProjectPreselect(projectParam);
      setModalOpen(true);
      setProjectParam(null);
    }
  }, [projectParam, setProjectParam]);

  return (
    <div className="flex h-full">
      {/* Session list sidebar */}
      <div className="flex w-64 flex-col border-r">
        <div className="flex items-center justify-between border-b p-3">
          <span className="text-sm font-semibold">会话列表</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setProjectPreselect(undefined);
              setModalOpen(true);
            }}
          >
            <Plus className="size-4" />
            新建
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessionsLoading ? (
            <p className="p-2 text-sm text-muted-foreground">加载中...</p>
          ) : sessions.length === 0 ? (
            <p className="p-2 text-sm text-muted-foreground">暂无会话</p>
          ) : (
            sessions.map((s) => (
              <SessionListItem
                key={s.id}
                session={s}
                active={sessionId === s.id}
                onClick={() => setSessionId(s.id)}
                onDelete={() => deleteSession(s.id)}
              />
            ))
          )}
        </div>
      </div>
      {/* Chat area */}
      <div className="flex-1">
        {sessionId ? (
          <Thread />
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <MessageSquare className="mx-auto mb-4 size-12 text-muted-foreground" />
              <p className="text-muted-foreground">选择一个会话或新建会话开始对话</p>
            </div>
          </div>
        )}
      </div>
      <NewSessionModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setProjectPreselect(undefined);
        }}
        onCreated={(id) => setSessionId(id)}
        preselectProjectId={projectPreselect}
      />
    </div>
  );
}

function SessionListItem({
  session,
  active,
  onClick,
  onDelete,
}: {
  session: Session;
  active: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const title =
    session.title ||
    (session.mode === "free" ? "自由学习" : session.project_name || "项目模式");

  return (
    <div
      onClick={onClick}
      className={cn(
        "group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "hover:bg-muted",
      )}
    >
      <div className="flex flex-col overflow-hidden">
        <span className="truncate font-medium">{title}</span>
        <span className="text-xs text-muted-foreground">
          {session.mode === "project" ? `📁 ${session.project_name}` : "💬 自由学习"}
        </span>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-destructive"
      >
        ✕
      </button>
    </div>
  );
}

function ReadOnlyChatContent({ sessionId }: { sessionId: string }) {
  // For read-only viewing, we set the threadId and render Thread
  // The readOnly prop on StreamProvider disables input
  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-4 py-2 text-sm text-muted-foreground">
        查看对话（只读）
      </div>
      <div className="flex-1">
        <Thread />
      </div>
    </div>
  );
}
```

Note: The `Thread` component from agent-chat-ui already handles rendering messages. For read-only mode, we need to modify it to conditionally hide the input area when `readOnly` is true. This modification should be done in `thread/index.tsx` by checking a context or prop.

- [ ] **Step 9: Adapt Thread component for readOnly mode**

In `frontend/src/components/chat/thread/index.tsx`, add a `readOnly` check. The Thread component should check if the StreamProvider is in readOnly mode (via a context or prop) and conditionally render the input area.

Add a `readOnly` export from StreamProvider and consume it in Thread:

In `StreamProvider.tsx`, add to the context:
```typescript
// Add readOnly to the context value or export a separate hook
export function useIsReadOnly() {
  // This can be a simple context or prop drilling
}
```

Actually, the simplest approach: pass `readOnly` through the StreamProvider context. In the `Thread` component, check `readOnly` and conditionally render the input form. If `readOnly` is true, skip rendering the input textarea and submit button.

- [ ] **Step 10: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Fix any import path issues in the copied thread components.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/components/chat/
git commit -m "feat: migrate chat module from agent-chat-ui

- SessionProvider replaces ThreadProvider (API Server data source)
- StreamProvider adapted for dynamic token from AuthProvider
- Thread components copied with updated imports
- NewSessionModal for session creation (free/project mode)
- ChatView: 3-column layout (sidebar + session list + chat)
- ReadOnly mode support for teacher viewing student conversations"
```

---

### Task 6: Chat Pages (Student + Teacher)

**Files:**
- Modify: `frontend/src/app/student/chat/page.tsx`
- Modify: `frontend/src/app/teacher/chat/page.tsx`

**Interfaces:**
- Consumes: `ChatView` from Task 5

- [ ] **Step 1: Create student chat page**

Replace `frontend/src/app/student/chat/page.tsx`:

```tsx
"use client";

import { ChatView } from "@/components/chat/ChatView";

export default function StudentChatPage() {
  return <ChatView role="student" />;
}
```

- [ ] **Step 2: Create teacher chat page**

Replace `frontend/src/app/teacher/chat/page.tsx`:

```tsx
"use client";

import { ChatView } from "@/components/chat/ChatView";

export default function TeacherChatPage() {
  return <ChatView role="teacher" />;
}
```

- [ ] **Step 3: Verify chat works**

```bash
cd frontend && npm run dev
```

Test: Login as student1, create a free session, send a message, verify AI responds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/student/chat/ frontend/src/app/teacher/chat/
git commit -m "feat: add student and teacher chat pages using shared ChatView"
```

---

### Task 7: Student Project Pages

**Files:**
- Create: `frontend/src/components/projects/ProjectList.tsx`
- Create: `frontend/src/components/projects/ProjectDetail.tsx`
- Modify: `frontend/src/app/student/projects/page.tsx`
- Modify: `frontend/src/app/student/projects/[id]/page.tsx`

**Interfaces:**
- Consumes: `projectsApi` from Task 2, Markdown rendering from chat module

- [ ] **Step 1: Create ProjectList component**

Create `frontend/src/components/projects/ProjectList.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { projectsApi } from "@/lib/api/projects";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Project } from "@/lib/types";

export function ProjectList({ readOnly = false }: { readOnly?: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi
      .list(readOnly ? "published" : undefined)
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [readOnly]);

  if (loading) return <div className="p-4">加载中...</div>;

  if (projects.length === 0) {
    return <div className="p-4 text-muted-foreground">暂无项目</div>;
  }

  return (
    <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link
          key={project.id}
          href={`${readOnly ? "/student" : "/teacher"}/projects/${project.id}`}
        >
          <Card className="transition-shadow hover:shadow-md">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{project.name}</CardTitle>
                <Badge variant={project.status === "published" ? "default" : "secondary"}>
                  {project.status === "published" ? "已发布" : "草稿"}
                </Badge>
              </div>
              <CardDescription className="line-clamp-2">
                {project.background_md.slice(0, 100)}
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create ProjectDetail component**

Create `frontend/src/components/projects/ProjectDetail.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api/projects";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import type { Project } from "@/lib/types";

export function ProjectDetail({
  id,
  readOnly = false,
}: {
  id: string;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi
      .get(id)
      .then(setProject)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-4">加载中...</div>;
  if (!project) return <div className="p-4">项目不存在</div>;

  const basePath = readOnly ? "/student" : "/teacher";

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push(`${basePath}/projects`)}
        className="mb-4"
      >
        <ArrowLeft className="mr-2 size-4" />
        返回列表
      </Button>
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <Badge variant={project.status === "published" ? "default" : "secondary"}>
            {project.status === "published" ? "已发布" : "草稿"}
          </Badge>
        </div>
      </div>
      <div className="prose prose-sm max-w-none">
        <h2 className="mb-3 text-lg font-semibold">项目背景</h2>
        <MarkdownText>
          {project.background_md}
        </MarkdownText>
      </div>
      {readOnly && (
        <div className="mt-8 border-t pt-4">
          <Button
            onClick={() =>
              router.push(`/student/chat?project=${project.id}`)
            }
          >
            在对话中讨论此项目
          </Button>
        </div>
      )}
    </div>
  );
}
```

Note: The `MarkdownText` component expects children to be a string. Check the actual signature in the copied `markdown-text.tsx` — it may accept `content` as a prop. Adapt accordingly.

- [ ] **Step 3: Wire up student project pages**

Replace `frontend/src/app/student/projects/page.tsx`:

```tsx
"use client";

import { ProjectList } from "@/components/projects/ProjectList";

export default function StudentProjectsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b px-4 py-3">
        <h1 className="text-xl font-bold">项目列表</h1>
      </div>
      <ProjectList readOnly />
    </div>
  );
}
```

Replace `frontend/src/app/student/projects/[id]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { ProjectDetail } from "@/components/projects/ProjectDetail";

export default function StudentProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ProjectDetail id={id} readOnly />;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/projects/ frontend/src/app/student/projects/
git commit -m "feat: add student project list and detail pages (read-only)

- ProjectList: card grid with status badges
- ProjectDetail: Markdown rendering of project background
- 'Discuss in chat' button navigates to chat with project pre-selected"
```

---

### Task 8: Teacher Project Management

**Files:**
- Create: `frontend/src/components/projects/ProjectFormModal.tsx`
- Create: `frontend/src/components/projects/ProjectTable.tsx`
- Modify: `frontend/src/app/teacher/projects/page.tsx`
- Modify: `frontend/src/app/teacher/projects/[id]/page.tsx`

**Interfaces:**
- Consumes: `projectsApi` from Task 2, `ProjectDetail` from Task 7

- [ ] **Step 1: Create ProjectFormModal**

Create `frontend/src/components/projects/ProjectFormModal.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { projectsApi } from "@/lib/api/projects";
import { toast } from "sonner";
import type { Project, ProjectStatus } from "@/lib/types";

export function ProjectFormModal({
  open,
  onClose,
  onSaved,
  project,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  project?: Project;
}) {
  const [name, setName] = useState("");
  const [backgroundMd, setBackgroundMd] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("draft");
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (project) {
      setName(project.name);
      setBackgroundMd(project.background_md);
      setStatus(project.status as ProjectStatus);
    } else {
      setName("");
      setBackgroundMd("");
      setStatus("draft");
    }
    setTab("edit");
  }, [project, open]);

  async function handleSave() {
    if (!name.trim() || !backgroundMd.trim()) {
      toast.error("项目名称和背景不能为空");
      return;
    }
    setLoading(true);
    try {
      if (project) {
        await projectsApi.update(project.id, {
          name,
          background_md: backgroundMd,
          status,
        });
        toast.success("项目已更新");
      } else {
        await projectsApi.create({
          name,
          background_md: backgroundMd,
          status,
        });
        toast.success("项目已创建");
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{project ? "编辑项目" : "新建项目"}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">项目名称</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入项目名称"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>项目背景 (Markdown)</Label>
            <div className="flex gap-2 border-b">
              <button
                className={cn("px-3 py-1 text-sm", tab === "edit" ? "border-b-2 border-primary font-medium" : "text-muted-foreground")}
                onClick={() => setTab("edit")}
              >
                编辑
              </button>
              <button
                className={cn("px-3 py-1 text-sm", tab === "preview" ? "border-b-2 border-primary font-medium" : "text-muted-foreground")}
                onClick={() => setTab("preview")}
              >
                预览
              </button>
            </div>
            {tab === "edit" ? (
              <Textarea
                value={backgroundMd}
                onChange={(e) => setBackgroundMd(e.target.value)}
                placeholder="## 项目描述&#10;请描述项目背景..."
                className="min-h-[200px] font-mono text-sm"
              />
            ) : (
              <div className="min-h-[200px] overflow-y-auto rounded-md border p-3">
                <MarkdownText>
                  {backgroundMd}
                </MarkdownText>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label>状态</Label>
            <RadioGroup
              value={status}
              onValueChange={(v) => setStatus(v as ProjectStatus)}
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="draft" id="draft" />
                <Label htmlFor="draft">草稿 (仅教师可见)</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="published" id="published" />
                <Label htmlFor="published">已发布 (学生可见)</Label>
              </div>
            </RadioGroup>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? "保存中..." : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

import { cn } from "@/lib/utils";
```

Note: The `cn` import at the bottom is a code smell — move it to the top of the file in actual implementation.

- [ ] **Step 2: Create ProjectTable component**

Create `frontend/src/components/projects/ProjectTable.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { projectsApi } from "@/lib/api/projects";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { ProjectFormModal } from "./ProjectFormModal";
import { toast } from "sonner";
import type { Project } from "@/lib/types";

export function ProjectTable() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | undefined>();

  function refresh() {
    setLoading(true);
    projectsApi
      .list()
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDelete(project: Project) {
    if (!confirm(`确定删除项目「${project.name}」吗？`)) return;
    try {
      await projectsApi.delete(project.id);
      toast.success("项目已删除");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">项目管理</h1>
        <Button
          onClick={() => {
            setEditingProject(undefined);
            setModalOpen(true);
          }}
        >
          <Plus className="mr-2 size-4" />
          新建项目
        </Button>
      </div>
      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">项目名称</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">创建时间</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} className="border-t">
                  <td className="px-4 py-2">
                    <Link
                      href={`/teacher/projects/${project.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={project.status === "published" ? "default" : "secondary"}>
                      {project.status === "published" ? "已发布" : "草稿"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(project.created_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setEditingProject(project);
                          setModalOpen(true);
                        }}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(project)}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ProjectFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={refresh}
        project={editingProject}
      />
    </div>
  );
}
```

- [ ] **Step 3: Wire up teacher project pages**

Replace `frontend/src/app/teacher/projects/page.tsx`:

```tsx
"use client";

import { ProjectTable } from "@/components/projects/ProjectTable";

export default function TeacherProjectsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <ProjectTable />
    </div>
  );
}
```

Replace `frontend/src/app/teacher/projects/[id]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { ProjectDetail } from "@/components/projects/ProjectDetail";

export default function TeacherProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <div className="h-full overflow-y-auto">
      <ProjectDetail id={id} />
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/projects/ frontend/src/app/teacher/projects/
git commit -m "feat: add teacher project management with full CRUD

- ProjectFormModal: create/edit with Markdown editor (edit/preview tabs)
- ProjectTable: list with inline edit/delete actions
- Status management: draft/published radio toggle"
```

---

### Task 9: Teacher Student Management

**Files:**
- Create: `frontend/src/components/students/StudentTable.tsx`
- Create: `frontend/src/components/students/StudentImportDialog.tsx`
- Create: `frontend/src/components/students/StudentSessionTable.tsx`
- Modify: `frontend/src/app/teacher/students/page.tsx`
- Modify: `frontend/src/app/teacher/students/[id]/page.tsx`

**Interfaces:**
- Consumes: `usersApi` from Task 2, `sessionsApi` from Task 2

- [ ] **Step 1: Create StudentTable**

Create `frontend/src/components/students/StudentTable.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usersApi } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Download, KeyRound, Trash2, Eye } from "lucide-react";
import { StudentImportDialog } from "./StudentImportDialog";
import { toast } from "sonner";
import type { Student } from "@/lib/types";

export function StudentTable() {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [importOpen, setImportOpen] = useState(false);

  function refresh() {
    setLoading(true);
    usersApi
      .listStudents()
      .then(setStudents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  const filtered = students.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.username.toLowerCase().includes(search.toLowerCase()),
  );

  async function handleResetPassword(student: Student) {
    if (!confirm(`确定重置「${student.name}」的密码为 123456 吗？`)) return;
    try {
      await usersApi.resetPassword(student.id);
      toast.success(`已重置 ${student.name} 的密码为 123456`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
    }
  }

  async function handleDelete(student: Student) {
    if (!confirm(`确定删除学生「${student.name}」吗？此操作不可撤销。`)) return;
    try {
      await usersApi.delete(student.id);
      toast.success("学生已删除");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function handleDownloadTemplate() {
    try {
      const blob = await usersApi.downloadTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "学生导入模板.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("下载模板失败");
    }
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">学生管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleDownloadTemplate}>
            <Download className="mr-2 size-4" />
            下载模板
          </Button>
          <Button onClick={() => setImportOpen(true)}>
            导入学生
          </Button>
        </div>
      </div>
      <Input
        placeholder="搜索学生姓名或学号..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 max-w-sm"
      />
      {loading ? (
        <p>加载中...</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">学号</th>
                <th className="px-4 py-2 text-left font-medium">姓名</th>
                <th className="px-4 py-2 text-left font-medium">创建时间</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((student) => (
                <tr key={student.id} className="border-t">
                  <td className="px-4 py-2">{student.username}</td>
                  <td className="px-4 py-2 font-medium">{student.name}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(student.created_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1">
                      <Link href={`/teacher/students/${student.id}`}>
                        <Button size="sm" variant="ghost">
                          <Eye className="mr-1 size-4" />
                          查看对话
                        </Button>
                      </Link>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleResetPassword(student)}
                      >
                        <KeyRound className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(student)}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <StudentImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={refresh}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create StudentImportDialog**

Create `frontend/src/components/students/StudentImportDialog.tsx`:

```tsx
"use client";

import { useState, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { usersApi } from "@/lib/api/users";
import { toast } from "sonner";
import { Upload, FileSpreadsheet } from "lucide-react";
import type { ImportResult } from "@/lib/types";

export function StudentImportDialog({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!/\.(xlsx|xls)$/i.test(selected.name)) {
        toast.error("请上传 .xlsx 或 .xls 文件");
        return;
      }
      setFile(selected);
      setResult(null);
    }
  }

  async function handleImport() {
    if (!file) {
      toast.error("请选择文件");
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await usersApi.import(formData);
      setResult(res);
      onImported();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "导入失败");
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    setFile(null);
    setResult(null);
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>导入学生</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="rounded-md border-2 border-dashed p-6 text-center">
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet className="size-8 text-green-500" />
                <p className="text-sm font-medium">{file.name}</p>
                <Button variant="ghost" size="sm" onClick={() => inputRef.current?.click()}>
                  重新选择
                </Button>
              </div>
            ) : (
              <div
                className="flex cursor-pointer flex-col items-center gap-2"
                onClick={() => inputRef.current?.click()}
              >
                <Upload className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  点击选择文件或拖拽到此处
                </p>
                <p className="text-xs text-muted-foreground">支持 .xlsx / .xls</p>
              </div>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
          {result && (
            <div className="rounded-md border p-4">
              <p className="font-medium">导入完成</p>
              <div className="mt-2 flex gap-4 text-sm">
                <span className="text-green-600">✅ 成功: {result.created}</span>
                <span className="text-yellow-600">⏭️ 跳过: {result.skipped}</span>
                <span className="text-muted-foreground">总计: {result.total}</span>
              </div>
              {result.errors.length > 0 && (
                <div className="mt-2">
                  <p className="text-sm text-red-600">错误详情:</p>
                  <ul className="ml-4 list-disc text-xs text-red-600">
                    {result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            {result ? "关闭" : "取消"}
          </Button>
          {!result && (
            <Button onClick={handleImport} disabled={loading || !file}>
              {loading ? "导入中..." : "导入"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Create StudentSessionTable**

Create `frontend/src/components/students/StudentSessionTable.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usersApi } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Eye } from "lucide-react";
import { useRouter } from "next/navigation";
import type { Session, Student } from "@/lib/types";

export function StudentSessionTable({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      usersApi.listStudents().then((students) => {
        const s = students.find((s) => s.id === studentId);
        if (s) setStudent(s);
      }),
      usersApi.getSessions(studentId).then(setSessions),
    ])
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) return <div className="p-4">加载中...</div>;

  return (
    <div className="p-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/teacher/students")}
        className="mb-4"
      >
        <ArrowLeft className="mr-2 size-4" />
        返回学生列表
      </Button>
      <div className="mb-6">
        <h1 className="text-xl font-bold">
          {student?.name} ({student?.username})
        </h1>
        <p className="text-sm text-muted-foreground">
          创建时间: {student && new Date(student.created_at).toLocaleDateString("zh-CN")}
        </p>
      </div>
      <h2 className="mb-3 text-lg font-semibold">会话记录</h2>
      {sessions.length === 0 ? (
        <p className="text-muted-foreground">暂无会话记录</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">会话标题</th>
                <th className="px-4 py-2 text-left font-medium">模式</th>
                <th className="px-4 py-2 text-left font-medium">项目</th>
                <th className="px-4 py-2 text-left font-medium">最后活跃</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id} className="border-t">
                  <td className="px-4 py-2 font-medium">
                    {session.title ||
                      (session.mode === "free" ? "自由学习" : "项目模式")}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={session.mode === "project" ? "default" : "secondary"}>
                      {session.mode === "project" ? "项目" : "自由"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {session.project_name || "-"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(session.last_active_at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-2">
                    <Link href={`/teacher/students/${studentId}/sessions/${session.id}`}>
                      <Button size="sm" variant="ghost">
                        <Eye className="mr-1 size-4" />
                        查看
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire up teacher student pages**

Replace `frontend/src/app/teacher/students/page.tsx`:

```tsx
"use client";

import { StudentTable } from "@/components/students/StudentTable";

export default function TeacherStudentsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <StudentTable />
    </div>
  );
}
```

Replace `frontend/src/app/teacher/students/[id]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { StudentSessionTable } from "@/components/students/StudentSessionTable";

export default function StudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <div className="h-full overflow-y-auto">
      <StudentSessionTable studentId={id} />
    </div>
  );
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/students/ frontend/src/app/teacher/students/
git commit -m "feat: add teacher student management

- StudentTable: list with search, reset password, delete, view conversations
- StudentImportDialog: Excel file upload with import results display
- StudentSessionTable: student's session list with view links
- Template download button"
```

---

### Task 10: Teacher Read-Only Conversation Viewing

**Files:**
- Create: `frontend/src/components/chat/ReadOnlyChatView.tsx`
- Modify: `frontend/src/app/teacher/students/[id]/sessions/[sid]/page.tsx`

**Interfaces:**
- Consumes: `sessionsApi` from Task 2, `createClient` from Task 5, chat thread components from Task 5

- [ ] **Step 1: Create ReadOnlyChatView**

Create `frontend/src/components/chat/ReadOnlyChatView.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { createClient } from "./client";
import { useAuth } from "@/components/auth/AuthProvider";
import { sessionsApi } from "@/lib/api/sessions";
import { Thread } from "./thread";
import { StreamProvider } from "./StreamProvider";
import { ArtifactProvider } from "./ArtifactProvider";
import { SessionProvider } from "./SessionProvider";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import type { Message } from "@langchain/langgraph-sdk";
import { AGENT_URL, ASSISTANT_ID } from "@/lib/constants";

interface ThreadState {
  values: { messages: Message[] };
}

export function ReadOnlyChatView({
  studentId,
  sessionId,
}: {
  studentId: string;
  sessionId: string;
}) {
  const router = useRouter();
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [sessionInfo, setSessionInfo] = useState<{
    title: string | null;
    mode: string;
    project_name: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        // Fetch session metadata from API Server
        const session = await sessionsApi.get(sessionId);
        setSessionInfo({
          title: session.title,
          mode: session.mode,
          project_name: session.project_name,
        });

        // Fetch thread state from Agent Server (read-only)
        const client = createClient(token);
        const state = await client.threads.getState(sessionId);
        setMessages(state.values?.messages ?? []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "加载对话失败",
        );
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [sessionId, token]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">加载对话中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">{error}</p>
          <Button
            variant="outline"
            onClick={() => router.push(`/teacher/students/${studentId}`)}
            className="mt-4"
          >
            返回
          </Button>
        </div>
      </div>
    );
  }

  const title =
    sessionInfo?.title ||
    (sessionInfo?.mode === "free"
      ? "自由学习"
      : sessionInfo?.project_name || "项目模式");

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push(`/teacher/students/${studentId}`)}
        >
          <ArrowLeft className="mr-2 size-4" />
          返回
        </Button>
        <span className="text-sm font-medium">
          查看对话: {title}
        </span>
        <span className="text-xs text-muted-foreground">(只读)</span>
      </div>
      <div className="flex-1 overflow-hidden">
        <ReadOnlyMessages messages={messages ?? []} />
      </div>
    </div>
  );
}

function ReadOnlyMessages({ messages }: { messages: Message[] }) {
  // Render messages using the same components as the chat thread
  // but without input/interaction capabilities
  // We can reuse the AI and Human message components directly
  
  // Import the message components
  const { AIMessage, HumanMessage } = require("./thread/messages");
  
  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-3xl space-y-4">
        {messages.map((msg, idx) => {
          const type = msg.type;
          if (type === "human") {
            return <HumanMessage key={idx} message={msg} />;
          }
          if (type === "ai") {
            return <AIMessage key={idx} message={msg} />;
          }
          return null;
        })}
      </div>
    </div>
  );
}
```

Note: The `require()` call should be replaced with proper ES module imports. The actual implementation should import `AIMessage` and `HumanMessage` (or equivalent) from the thread messages module at the top of the file. Check the exact export names from the copied `thread/messages/` directory and adapt.

- [ ] **Step 2: Wire up the read-only conversation page**

Replace `frontend/src/app/teacher/students/[id]/sessions/[sid]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { ReadOnlyChatView } from "@/components/chat/ReadOnlyChatView";

export default function StudentSessionViewPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = use(params);
  return (
    <div className="h-full">
      <ReadOnlyChatView studentId={id} sessionId={sid} />
    </div>
  );
}
```

- [ ] **Step 3: Fix ReadOnlyChatView imports**

Replace the `require()` call in `ReadOnlyChatView.tsx` with proper imports. Check the actual exports from `thread/messages/` directory. The components are likely exported from `thread/messages/ai.tsx` and `thread/messages/human.tsx`.

At the top of `ReadOnlyChatView.tsx`, add:

```typescript
import { AIMessage, HumanMessage } from "./thread/messages";
```

And remove the `require()` line and use the imported components directly.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ReadOnlyChatView.tsx frontend/src/app/teacher/students/
git commit -m "feat: add teacher read-only conversation viewing

- ReadOnlyChatView: fetches thread state via LangGraph SDK
- Renders messages with shared components (no input/interaction)
- Header shows session title and read-only indicator
- Back button returns to student session list"
```

---

### Task 11: E2E Testing with agent-browser

**Files:**
- Create: `docs/superpowers/e2e-report.md`

**Interfaces:**
- Consumes: All previous tasks, agent-browser skill

- [ ] **Step 1: Load agent-browser skill**

```bash
# The agent-browser skill is loaded via the skill tool
# It provides browser automation CLI commands
```

- [ ] **Step 2: Start frontend dev server**

```bash
cd frontend && npm run dev &
```

Ensure both backends are running:
- API Server on :8000
- Agent Server on :2024

- [ ] **Step 3: Run E2E test scenarios**

Execute each test scenario from the spec using agent-browser automation:

1. **Login as student**: Navigate to localhost:3000, verify redirect to /login, fill username=student1 password=student123, verify redirect to /student/chat
2. **Login as teacher**: Logout, login as teacher1/teacher123, verify redirect to /teacher/chat
3. **Route guard**: Clear auth, visit /student/chat, verify redirect to /login
4. **Role isolation**: Login as student, visit /teacher/students, verify redirect to /student/chat
5. **Create session**: Login as student, click "新建", select "自由学习模式", click "创建", verify session appears in list
6. **Send message**: Type a message in the input, send, verify AI streams a response
7. **View projects**: Navigate to /student/projects, verify project cards display
8. **Project detail**: Click a project, verify Markdown rendering
9. **Teacher project CRUD**: Login as teacher, create a project, edit it, publish it, verify student can see it
10. **Student list**: Navigate to /teacher/students, verify student table
11. **View student conversation**: Click "查看对话" on a student, click "查看" on a session, verify read-only chat displays
12. **Logout**: Click logout, verify redirect to /login

- [ ] **Step 4: Record test results**

Create `docs/superpowers/e2e-report.md` with test results:

```markdown
# E2E Test Report

**Date**: 2026-07-23
**Tool**: agent-browser
**Frontend**: localhost:3000

## Test Results

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1 | Login as student | ✅/❌ | ... |
| 2 | Login as teacher | ✅/❌ | ... |
... (all 16 scenarios)
```

- [ ] **Step 5: Commit test report**

```bash
git add docs/superpowers/e2e-report.md
git commit -m "docs: E2E test report for production frontend"
```

---

## Self-Review Checklist

### Spec Coverage
- [x] Login page + route guard -> Task 3, Task 4
- [x] Role-prefixed routing -> Task 4
- [x] Token in localStorage + flag cookies -> Task 3
- [x] SessionProvider replaces ThreadProvider -> Task 5
- [x] StreamProvider with dynamic token -> Task 5
- [x] Chat module migration from agent-chat-ui -> Task 5
- [x] Three-column chat layout -> Task 5 (ChatView)
- [x] New session creation flow (free/project) -> Task 5 (NewSessionModal)
- [x] Student chat page -> Task 6
- [x] Student project list (read-only) -> Task 7
- [x] Student project detail with Markdown -> Task 7
- [x] "Discuss in chat" button -> Task 7 (ProjectDetail)
- [x] Teacher chat page -> Task 6
- [x] Teacher project CRUD -> Task 8
- [x] Teacher project form with Markdown editor -> Task 8 (ProjectFormModal)
- [x] Teacher student list -> Task 9
- [x] Teacher Excel import -> Task 9 (StudentImportDialog)
- [x] Teacher reset password -> Task 9
- [x] Teacher delete student -> Task 9
- [x] Teacher view student sessions -> Task 9 (StudentSessionTable)
- [x] Teacher read-only conversation viewing -> Task 10
- [x] E2E testing with agent-browser -> Task 11

### Type Consistency
- `Session.id` used consistently as thread_id in StreamProvider, SessionProvider, and ReadOnlyChatView
- `SessionCreate` matches API schema (mode, project_id - no title field)
- `UserOut` fields match types.ts
- `LoginResponse` fields match types.ts
- `ImportResult` fields match types.ts
- `ProjectOut` fields match types.ts

### Placeholder Scan
- Task 5 Step 5/6: Thread component adaptation requires manual import fixing - documented with exact search commands
- Task 5 Step 9: ReadOnly mode in Thread component - described approach but exact code depends on Thread component structure
- Task 10 Step 1: require() call needs to be replaced with proper import - documented in Step 3
- All other steps have complete code
