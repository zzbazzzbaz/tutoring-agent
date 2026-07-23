# Production Frontend Design

**Date**: 2026-07-23
**Status**: Approved (pending spec review)
**Author**: Brainstorming session

## Overview

A production Next.js frontend for the Teaching Agent platform, replacing the test-only `agent-chat-ui`. The frontend serves two roles (student and teacher) with role-prefixed routing, reusing the tech stack and chat module from `test_frontend/agent-chat-ui`.

## Context

### Current State

- **Test frontend** (`test_frontend/agent-chat-ui`): Pure chat UI with hardcoded Bearer token. No login, session management, or project/student management. Based on LangChain's `agent-chat-ui`.
- **Agent Server** (`services/agent_server`, port 2024): LangGraph Server for streaming chat, thread management, and quiz interrupts.
- **API Server** (`services/api_server`, port 8000): FastAPI backend for auth, users, projects, and sessions. `session.id` maps 1:1 to LangGraph `thread_id`.

### Tech Stack (reused from agent-chat-ui)

| Category | Technology | Version |
|----------|-----------|---------|
| Framework | Next.js (App Router) | ^15.5.18 |
| Language | TypeScript | ~5.8.3 |
| UI Library | React | ^19.2.5 |
| AI SDK | @langchain/langgraph-sdk | ^1.8.10 |
| UI Components | shadcn/ui (new-york) + Radix UI | ^1.x |
| Styling | Tailwind CSS v4 + tailwindcss-animate | ^4.2.4 |
| URL State | nuqs | ^2.8.9 |
| Animation | framer-motion | ^12.38.0 |
| Markdown | react-markdown + remark-gfm + remark-math + rehype-katex | latest |
| Code Highlight | react-syntax-highlighter | ^15.6.1 |
| Math | katex | ^0.16.45 |
| Notifications | sonner | ^2.0.7 |
| Icons | lucide-react | ^0.476.0 |

## Requirements

### Student Features

1. **Chat**: Create sessions (free mode or project mode), stream conversations with AI, handle quiz interrupts
2. **View Projects**: Browse published projects, view project details (Markdown background)

### Teacher Features

1. **Chat**: Create own sessions (free mode or project mode), same chat experience as students
2. **Project Management**: Full CRUD (create, read, update, delete) + status management (draft/published) with Markdown editor
3. **Student Management**: List students, batch import (Excel), delete students, reset passwords, view student conversation history (read-only)

### Cross-cutting

- Login page with username/password authentication
- Role-based route guards (middleware + layout-level)
- Token stored in localStorage (for Agent Server direct-connect) + flag cookies (for middleware)
- Session creation via API Server before connecting to Agent Server

## Architecture

### App Structure: Role-Prefixed Routing (Single App)

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── components.json
├── .env
├── src/
│   ├── app/
│   │   ├── login/page.tsx
│   │   ├── student/
│   │   │   ├── layout.tsx                # Student layout (sidebar + role guard)
│   │   │   ├── chat/page.tsx             # Student chat
│   │   │   └── projects/
│   │   │       ├── page.tsx              # Project list (read-only)
│   │   │       └── [id]/page.tsx         # Project detail (read-only)
│   │   ├── teacher/
│   │   │   ├── layout.tsx                # Teacher layout (sidebar + role guard)
│   │   │   ├── chat/page.tsx             # Teacher chat
│   │   │   ├── projects/
│   │   │   │   ├── page.tsx              # Project management (CRUD)
│   │   │   │   └── [id]/page.tsx         # Project detail/edit
│   │   │   └── students/
│   │   │       ├── page.tsx              # Student list + import
│   │   │       └── [id]/
│   │   │           ├── page.tsx          # Student detail (session list)
│   │   │           └── sessions/[sid]/page.tsx  # View student conversation (read-only)
│   │   ├── layout.tsx                    # Root layout
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                           # shadcn/ui base (copied from agent-chat-ui)
│   │   ├── chat/                         # Shared chat module
│   │   │   ├── thread/                   # Thread components (messages, input, interrupts)
│   │   │   ├── StreamProvider.tsx        # Streaming Provider (token from AuthProvider)
│   │   │   ├── SessionProvider.tsx       # Session list (API Server data source)
│   │   │   ├── ArtifactProvider.tsx      # Artifact panel (copied as-is)
│   │   │   └── client.ts                 # LangGraph SDK Client factory
│   │   ├── auth/
│   │   │   ├── AuthProvider.tsx          # Auth context (token management)
│   │   │   ├── RoleGuard.tsx             # Role guard wrapper
│   │   │   └── LoginForm.tsx
│   │   ├── projects/
│   │   │   ├── ProjectList.tsx           # List (supports read-only and CRUD modes)
│   │   │   ├── ProjectDetail.tsx         # Detail (supports read-only and edit modes)
│   │   │   └── ProjectForm.tsx           # Create/edit form (with Markdown editor)
│   │   ├── students/
│   │   │   ├── StudentList.tsx           # Student table
│   │   │   ├── StudentImport.tsx         # Excel import dialog
│   │   │   └── StudentSessionList.tsx    # Student session list
│   │   └── layout/
│   │       ├── Sidebar.tsx               # App navigation sidebar
│   │       └── PageContainer.tsx
│   ├── hooks/
│   │   ├── use-file-upload.tsx           # Copied from agent-chat-ui
│   │   ├── useMediaQuery.tsx             # Copied from agent-chat-ui
│   │   └── use-session.tsx              # Session management hook
│   ├── lib/
│   │   ├── api/                          # API Server HTTP client
│   │   │   ├── client.ts                 # Base client (Bearer token injection)
│   │   │   ├── auth.ts                   # Auth API
│   │   │   ├── sessions.ts              # Session API
│   │   │   ├── projects.ts              # Project API
│   │   │   └── users.ts                 # User API
│   │   ├── utils.ts                      # Copied from agent-chat-ui
│   │   ├── multimodal-utils.ts           # Copied from agent-chat-ui
│   │   ├── agent-inbox-interrupt.ts      # Copied from agent-chat-ui
│   │   ├── ensure-tool-responses.ts      # Copied from agent-chat-ui
│   │   └── constants.ts                  # Constants (routes, storage keys)
│   └── middleware.ts                     # Next.js middleware (route guard)
└── public/
```

### Authentication

#### Login Flow

1. User visits any page
2. `middleware.ts` checks `tutoring_auth` cookie
3. No cookie -> redirect to `/login`
4. Cookie exists but role mismatch -> redirect to correct role route
5. Pass -> render page

On login page:
1. User enters username + password
2. `POST /auth/login` (API Server) -> returns `{ token, user: { id, username, role, name } }`
3. Store in `localStorage`: `tutoring_token` (token), `tutoring_user` (user JSON)
4. Set cookies: `tutoring_auth=1`, `tutoring_role={role}` (path=/)
5. Redirect by role: student -> `/student/chat`, teacher -> `/teacher/chat`

#### Token Storage (Dual Storage)

| Storage | Key | Content | Purpose |
|---------|-----|---------|---------|
| `localStorage` | `tutoring_token` | Bearer token | Client-side API calls + Agent Server SDK |
| `localStorage` | `tutoring_user` | User JSON (id, username, role, name) | UI display |
| Cookie | `tutoring_auth` | `1` | Middleware auth check (flag only) |
| Cookie | `tutoring_role` | `student` or `teacher` | Middleware role routing (flag only) |

Cookies are routing hints only, not security boundaries. Actual authorization is enforced by API Server and Agent Server on every request via Bearer token verification.

#### AuthProvider

```typescript
interface AuthContextValue {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login(username: string, password: string): Promise<void>;
  logout(): Promise<void>;
}
```

On mount: reads token from `localStorage`, calls `GET /auth/me` to verify. If invalid, clears storage + cookies, redirects to `/login`.

#### Route Guards

**middleware.ts** (server-side, runs on every request):
- `/login` + already authenticated -> redirect to role home
- Non-`/login` + not authenticated -> redirect to `/login`
- `/student/*` + role=teacher -> redirect to `/teacher/chat`
- `/teacher/*` + role=student -> redirect to `/student/chat`

**Layout-level guards** (client-side, double protection):
- `student/layout.tsx`: checks AuthProvider, if role !== 'student' -> redirect
- `teacher/layout.tsx`: checks AuthProvider, if role !== 'teacher' -> redirect

#### Logout Flow

1. `POST /auth/logout` (API Server, deletes DB token record)
2. Clear `localStorage` (`tutoring_token`, `tutoring_user`)
3. Clear cookies (`tutoring_auth`, `tutoring_role`)
4. Redirect to `/login`

### API Layer

#### Dual Client Architecture

```
Frontend (Next.js)
  |
  +-- API Client (fetch wrapper)
  |     Base: http://localhost:8000 (NEXT_PUBLIC_API_URL)
  |     Auth: Bearer token from localStorage
  |     Endpoints: /auth/*, /sessions/*, /projects/*, /users/*
  |     Error handling: 401 -> auto logout, 403 -> toast error
  |
  +-- Agent Client (@langchain/langgraph-sdk)
        Base: http://localhost:2024 (NEXT_PUBLIC_AGENT_URL)
        Auth: Bearer token from AuthProvider
        Usage: useStream() for active chat, threads.getState() for read-only
```

#### API Client (`lib/api/client.ts`)

```typescript
class ApiClient {
  private baseUrl: string;
  
  // Auto-inject Bearer token from localStorage
  // 401 response -> auto logout + redirect /login
  // Unified error handling: { detail: { error: { code, message } } }
  
  async get<T>(path: string): Promise<T>;
  async post<T>(path: string, body?: unknown): Promise<T>;
  async patch<T>(path: string, body: unknown): Promise<T>;
  async delete<T>(path: string): Promise<T>;
}
```

Module wrappers:
- `lib/api/auth.ts`: login, logout, me, changePassword
- `lib/api/sessions.ts`: createSession, listSessions, getSession, deleteSession
- `lib/api/projects.ts`: createProject, listProjects, getProject, updateProject, deleteProject
- `lib/api/users.ts`: listStudents, listTeachers, deleteStudent, resetPassword, importStudents, downloadTemplate, getStudentSessions

#### Agent Client (`components/chat/client.ts`)

Migrated from agent-chat-ui. Key change: token sourced dynamically from AuthProvider (instead of `NEXT_PUBLIC_AUTH_TOKEN` env var).

### State Management (Provider Hierarchy)

```
AuthProvider (outermost)
  |-- Provides token to all children
  |
  +-- SessionProvider (replaces ThreadProvider)
  |     Data source: API Server GET /sessions
  |     Provides: sessions[], createSession(), deleteSession(), refreshSessions()
  |     Teacher mode: GET /users/{id}/sessions for viewing student sessions
  |
  +-- StreamProvider (migrated from agent-chat-ui)
  |     Uses @langchain/langgraph-sdk useStream hook
  |     Token from AuthProvider
  |     Supports readOnly prop (for teacher viewing student conversations)
  |     onThreadId -> update URL + refresh session list
  |
  +-- ArtifactProvider (copied as-is from agent-chat-ui)
        Artifact panel toggle + context management
```

#### ThreadProvider -> SessionProvider Migration

| Dimension | Original ThreadProvider | New SessionProvider |
|-----------|------------------------|---------------------|
| Data source | Agent Server `client.threads.search()` | API Server `GET /sessions` |
| Metadata | thread_id, created_at | session_id, mode, title, project_id, last_active_at, created_at |
| Create | Agent Server `client.threads.create()` | API Server `POST /sessions` |
| Delete | Agent Server `client.threads.delete()` | API Server `DELETE /sessions/{id}` |
| Filter | metadata: { graph_id } | Returns current user's sessions directly |

### Chat Module (Shared)

#### Components Migrated from agent-chat-ui

| Source | Target | Changes |
|--------|--------|---------|
| `providers/Stream.tsx` | `components/chat/StreamProvider.tsx` | Token from AuthProvider |
| `providers/Artifact.tsx` | `components/chat/ArtifactProvider.tsx` | None (direct copy) |
| `providers/client.ts` | `components/chat/client.ts` | Dynamic token injection |
| `components/thread/index.tsx` | `components/chat/thread/index.tsx` | Adapt to SessionProvider, add readOnly |
| `components/thread/messages/*` | `components/chat/thread/messages/*` | None (direct copy) |
| `components/thread/markdown-text.tsx` | `components/chat/thread/markdown-text.tsx` | None (direct copy) |
| `components/thread/artifact.tsx` | `components/chat/thread/artifact.tsx` | None (direct copy) |
| `hooks/use-file-upload.tsx` | `hooks/use-file-upload.tsx` | None (direct copy) |
| `lib/utils.ts`, `lib/multimodal-utils.ts`, etc. | `lib/` | None (direct copy) |

#### Chat Page Layout (Three Columns)

```
+----------+--------------+-------------------------------+
| App      | Session List | Chat Area                     |
| Sidebar  |              |                               |
|          | + New Session|  AI: Hello, how can I help?   |
| > Chat   | |----------| |                               |
|   Projects| | Free     | |  Human: What is TCP handshake?|
|   Students| | 2m ago   | |                               |
|          | |----------| |  AI: Let's think about...     |
|          | | Project  | |                               |
| -------- | | 1h ago   | |  +---------------------+      |
| student1 | |----------| |  | [Type message...] [>|]      |
| Logout   |              |  +---------------------+      |
+----------+--------------+-------------------------------+
```

- **App Sidebar** (240px): Role navigation (Chat/Projects/Students) + user info + logout
- **Session List** (260px, collapsible): Session list + new button, shows title/mode/time
- **Chat Area** (flex-1): Message list + input + Artifact panel

Mobile: Session List collapses to Sheet (reusing framer-motion animation from agent-chat-ui).

#### New Session Creation Flow

1. Click "+ New Session" -> modal appears
2. Mode selection: Free Learning / Project Mode
3. If Project Mode: dropdown to select published project
4. Optional session title
5. Click Create -> `POST /sessions { mode, project_id?, title? }`
6. Get session_id (= thread_id)
7. useStream connects to Agent Server, chat begins
8. Session list refreshes

#### Teacher Read-Only Conversation Viewing

```
/teacher/students/[id]/sessions/[sid]
  |
  +-- GET /sessions/{sid} (API Server) -> session metadata
  +-- client.threads.getState(sid) (Agent Server) -> message history
  |     state.values.messages = complete conversation
  +-- Render with same message components, but:
        - No input box
        - No "new session" button
        - No regenerate/edit message
        - Header shows "Viewing {student name}'s conversation"
```

#### StreamProvider Adaptation

```typescript
<StreamProvider
  threadId={sessionId}
  assistantId="tutor"
  readOnly={isReadOnly}
  onThreadCreated={(id) => router.push(`/${role}/chat?session=${id}`)}
>
  <ChatView />
</StreamProvider>
```

Key changes:
1. Token from AuthProvider (not env var)
2. New `readOnly` prop to disable input
3. `onThreadId` callback updates URL with session_id

### Student Pages

#### Student Navigation

```
App Sidebar (Student)
+-- > Chat      -> /student/chat
+--   Projects  -> /student/projects
+-- Bottom: student name + logout
```

#### Project List (`/student/projects`)

- `GET /projects` (optionally `?status=published`)
- Card grid: project name + status badge
- Click card -> detail page

#### Project Detail (`/student/projects/[id]`)

- `GET /projects/{id}`
- `background_md` rendered with existing Markdown component (`markdown-text.tsx`)
- "Discuss in chat" button: navigate to `/student/chat?project={id}` (auto-opens new session modal with project pre-selected)

### Teacher Pages

#### Teacher Navigation

```
App Sidebar (Teacher)
+--   Chat      -> /teacher/chat
+--   Projects  -> /teacher/projects
+-- > Students  -> /teacher/students
+-- Bottom: teacher name + logout
```

#### Project Management (`/teacher/projects`)

- Table view: name, status, created_at, actions (edit, delete)
- Status filter (all/draft/published)
- "New Project" button -> modal form

#### Project Create/Edit Modal

- Form fields: name (input), background_md (Markdown editor with edit/preview tabs), status (draft/published radio)
- Markdown editor: textarea + tab toggle to preview (reuses `markdown-text.tsx` for rendering)
- Save: `POST /projects` or `PATCH /projects/{id}`
- Delete: confirmation dialog -> `DELETE /projects/{id}` (soft delete)

#### Student List (`/teacher/students`)

- `GET /users/students`
- Table: username, name, created_at, actions
- "Import Students" button -> file upload dialog
- "Download Template" button -> `GET /users/students/template` (Excel download)
- Actions per student: View Conversations, Reset Password, Delete

#### Excel Import

- File upload (.xlsx/.xls) via drag-and-drop or file picker
- `POST /users/students/import` (multipart/form-data)
- Display import results: success count + error details
- Template download: `GET /users/students/template`

#### Student Detail (`/teacher/students/[id]`)

- Student info (name, username, created_at)
- `GET /users/{id}/sessions` -> session list
- Table: title, mode, project, last_active_at, "View" link
- "View" -> `/teacher/students/{id}/sessions/{sid}` (read-only conversation)

#### Student Conversation View (`/teacher/students/[id]/sessions/[sid]`)

- `GET /sessions/{sid}` (API Server) -> session metadata
- `client.threads.getState(sid)` (Agent Server) -> message history
- Read-only rendering with same chat components (no input box, no actions)

### Teacher API Endpoints

| Feature | Endpoint | Method |
|---------|----------|--------|
| Project CRUD | `/projects[/{id}]` | POST/GET/PATCH/DELETE |
| Student list | `/users/students` | GET |
| Student sessions | `/users/{id}/sessions` | GET |
| Import students | `/users/students/import` | POST (multipart) |
| Download template | `/users/students/template` | GET |
| Reset password | `/users/{id}/reset-password` | POST |
| Delete student | `/users/{id}` | DELETE |
| View conversation | Agent Server `threads.getState(sid)` | GET (SDK) |

## Testing Strategy

### Tool: agent-browser skill

Browser automation CLI for E2E testing: navigating pages, filling forms, clicking buttons, screenshots, extracting data.

### Test Environment

- API Server (:8000) - running
- Agent Server (:2024) - running
- Frontend dev server (:3000)
- Seed data: teacher1/teacher123, student1/student123, student2/student123

### Test Scenarios

| # | Scenario | Role | Key Assertions |
|---|----------|------|----------------|
| 1 | Login | Student | Redirect to /student/chat |
| 2 | Login | Teacher | Redirect to /teacher/chat |
| 3 | Route guard | Unauthenticated | /student/chat -> /login |
| 4 | Role isolation | Student | /teacher/students -> /student/chat |
| 5 | Create session | Student | Session appears in list |
| 6 | Send message | Student | AI streams response |
| 7 | Quiz interrupt | Student | Interrupt UI renders, answer submits |
| 8 | Project mode | Student | Project background injected into context |
| 9 | View projects | Student | List + detail Markdown rendering |
| 10 | Project CRUD | Teacher | Create, edit, publish, verify student visibility |
| 11 | Delete project | Teacher | List updates after deletion |
| 12 | Student list | Teacher | Table displays students |
| 13 | Import students | Teacher | Excel upload + result display |
| 14 | Reset password | Teacher | Toast confirmation |
| 15 | View student conversation | Teacher | Read-only chat displays messages |
| 16 | Logout | Any | Redirect to /login |

Test report saved to `docs/superpowers/e2e-report.md`.

## Environment Configuration

```env
# frontend/.env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_AGENT_URL=http://127.0.0.1:2024
NEXT_PUBLIC_ASSISTANT_ID=tutor
```

## Key Design Decisions

1. **Role-prefixed routing** (`/student/*`, `/teacher/*`): Simple middleware guards, self-documenting URLs, clean role isolation.
2. **Dual token storage** (localStorage + flag cookies): localStorage for client-side Agent Server access, cookies for middleware route guarding. Cookies are flags only, not security boundaries.
3. **SessionProvider replaces ThreadProvider**: API Server is the source of truth for session metadata (title, mode, project_id, last_active_at), richer than Agent Server's thread metadata.
4. **Session creation via API Server first**: `POST /sessions` -> get session_id -> connect to Agent Server. Maintains the 1:1 session_id/thread_id mapping.
5. **Teacher read-only via `threads.getState()`**: Uses LangGraph SDK to fetch thread state (message history) without creating a run. Auth middleware allows `access=read` for teachers.
6. **Chat components shared, pages wrapped per role**: Core chat components are shared. `student/chat` and `teacher/chat` pages are thin wrappers around the same `<ChatView />` component.
7. **Markdown editor**: Textarea + tabbed preview (edit/preview toggle), reusing existing `markdown-text.tsx` for rendering. No heavy editor library.
